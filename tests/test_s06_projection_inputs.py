"""Invented raw-projection custody controls; no likelihood or native call."""
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from reproduction.score_replay.core import Inputs,digest
from reproduction.score_replay.regional_replay import archived_california_projection,projection_difference


class ProjectionInputControls(unittest.TestCase):
    def test_signed_zero_is_numerically_equal_but_not_byte_exact(self):
        report=projection_difference(np.array([0.]),np.array([-0.]))
        self.assertFalse(report['byte_exact'])
        self.assertNotEqual(report['live_sha256'],report['archived_sha256'])
        self.assertEqual(report['maximum_absolute_delta'],0.)
        self.assertEqual(report['changed_values'],0)

    def fixture(self,root):
        arrays=dict(source_event_indices=np.array([0,1],dtype=np.int64),t_days=np.array([0.,1.]),
            latitude=np.array([10.,11.]),longitude=np.array([20.,21.]),xy_km=np.array([[0.,0.],[1.,1.]]),
            K=np.array([1.,2.]),cell_id=np.array([0.,1.]),rectangles=np.array([[0.,2.,0.,2.]]),
            cell_areas=np.array([4.]),centers=np.array([[1.,1.]]),coverage_end_days=np.asarray(2.))
        handle=io.BytesIO();np.savez_compressed(handle,**arrays);raw=handle.getvalue();(root/'projection.npz').write_bytes(raw)
        projection=dict(path='projection.npz',sha256=digest(raw),bytes=len(raw))
        prov=dict(projection_sha256=projection['sha256'],catalogue_sha256='cohort',geometry_sha256='geometry')
        raw=json.dumps(prov).encode();(root/'provenance.json').write_bytes(raw)
        row=dict(projection=projection,projection_provenance=dict(path='provenance.json',sha256=digest(raw)),
                 catalogue=dict(sha256='cohort'),geometry=dict(sha256='geometry'))
        hashes={k:digest(np.ascontiguousarray(a,dtype='float64').tobytes()) for k,a in
            [('parent_xy',arrays['xy_km']),('event_xy',arrays['xy_km'][1:]),('rectangles',arrays['rectangles']),('cell_areas',arrays['cell_areas'])]}
        state=dict(start=1.,end=2.,original_feature_metadata=dict(array_sha256=hashes))
        values=[np.array([0.,1.,3.]),np.array([.1,.2,.3]),np.array([10.,11.,12.]),np.array([20.,21.,22.]),
            np.array([0,1,2]),np.array([[0.,0.],[1.,1.],[2.,2.]]),arrays['rectangles'].copy(),arrays['cell_areas'].copy(),arrays['centers'].copy()]
        return Inputs(root),row,state,values

    def test_original_projection_used_and_live_differences_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,row,state,values=self.fixture(root)
            values[5][1,0]+=1e-12
            result,rect,area,centers=archived_california_projection(inputs,row,state,*values,root)
            self.assertEqual(result['xy_km'][1,0],1.)
            self.assertEqual(len(result['t_days']),2)
            report=json.loads((root/'projection_diagnostics.json').read_text())
            self.assertTrue(report['raw_event_binding_exact']);self.assertEqual(report['unused_later_raw_rows'],1)
            difference=report['live_platform_comparison']['xy_km']
            self.assertFalse(difference['byte_exact']);self.assertGreater(difference['maximum_absolute_delta'],0.)
            self.assertEqual(difference['maximum_difference_index'],[1,0])
            self.assertNotEqual(difference['live_sha256'],difference['archived_sha256'])

    def test_raw_event_binding_and_interval_are_exact(self):
        for mutation in ('time','latitude','mark','cell','interval','original_hash'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);inputs,row,state,values=self.fixture(root)
                if mutation=='time':values[0][0]=.01
                elif mutation=='latitude':values[2][0]+=1e-12
                elif mutation=='mark':values[1][0]+=.01
                elif mutation=='cell':values[4][0]=1
                elif mutation=='interval':state['end']=3.
                else:state['original_feature_metadata']['array_sha256']['parent_xy']='wrong'
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    archived_california_projection(inputs,row,state,*values,root)

    def test_input_bytes_and_geometry_cannot_be_substituted(self):
        for mutation in ('bytes','geometry','missing'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);inputs,row,state,values=self.fixture(root)
                if mutation=='bytes':(root/'projection.npz').write_bytes(b'changed')
                elif mutation=='geometry':row['geometry']['sha256']='wrong'
                else:del row['projection']
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    archived_california_projection(inputs,row,state,*values,root)

    def test_nonfinite_and_wrong_shape_live_projection_rejected(self):
        for value in (np.array([[float('nan'),0.]]),np.zeros((2,2))):
            with self.assertRaises(ValueError):projection_difference(value,np.zeros((1,2)))


if __name__=='__main__':unittest.main()
