"""Atomic disk-backed stores for large recovery training matrices."""

from __future__ import annotations

from dataclasses import fields,replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Final, Mapping,Sequence
import weakref

import numpy as np

from . import common as C
from .exact_delayed_teacher import (
    TEACHER_DAY_SCHEMA,ExactDelayedTeacherDay,
)
from .tabular_delayed_corpus import (
    FEATURE_SHARD_SCHEMA,CausalFeatureShard,project_feature_schema,
)
from .tabular_action_features import ACTION_STATE_FEATURE_NAMES
from .tabular_recovery_contracts import (
    COMPONENT_STACK_NAMES,CausalFeatureSchema,RecoveryRefusal,VALUE_SCALE_USD,
)
from .tabular_recovery_contracts import POLICY_ACTIONS,validate_model_feature_names
from .tabular_training import (
    ActionTrainingMatrix,ComponentPredictionTable,ComponentTrainingMatrix,
    assemble_action_training_matrix,assemble_component_training_matrix,
)


COMPONENT_STORE_SCHEMA: Final = "QRE2TABCOMPONENTSTORE2"
ACTION_STORE_SCHEMA: Final = "QRE2TABACTIONSTORE2"
DAY_STORE_INDEX_SCHEMA: Final = "QRE2TABDAYSTOREINDEX1"
PROJECTION_RECEIPT_SCHEMA: Final = "QRE2TABPROJECTIONRECEIPT1"
_COMPONENT_ARRAYS: Final = tuple(
    field.name for field in fields(ComponentTrainingMatrix)
    if field.name not in {"feature_names", "source_receipts"})
_ACTION_ARRAYS: Final = tuple(
    field.name for field in fields(ActionTrainingMatrix)
    if field.name not in {
        "feature_names", "component_oof_receipt_sha256", "source_receipts",
        "forced_occupied_rows_omitted"})
_VALIDATION_CELLS_PER_CHUNK: Final = 4_000_000
_TRUSTED_ARRAYS: dict[int,weakref.ReferenceType[object]] = {}
_STRING_SEQUENCE_DIGESTS: dict[
    int,tuple[weakref.ReferenceType[object],str]] = {}


def _array_chain(value:np.ndarray):
    """Yield ndarray owners without retaining mmap/file handles globally."""

    current:object=value;seen:set[int]=set()
    while isinstance(current,np.ndarray) and id(current) not in seen:
        seen.add(id(current));yield current
        current=getattr(current,"base",None)


def _trust_array(value:np.ndarray)->None:
    for current in _array_chain(value):
        identity=id(current)
        try:
            def discard(reference:weakref.ReferenceType[object],*,
                        key:int=identity)->None:
                if _TRUSTED_ARRAYS.get(key) is reference:
                    _TRUSTED_ARRAYS.pop(key,None)
            _TRUSTED_ARRAYS[identity]=weakref.ref(current,discard)
        except TypeError:
            continue


def _array_is_trusted(value:np.ndarray)->bool:
    for current in _array_chain(value):
        reference=_TRUSTED_ARRAYS.get(id(current))
        if reference is not None and reference() is current:return True
    return False


def _all_finite_bounded(value:np.ndarray)->bool:
    array=np.asarray(value)
    if not array.size:return True
    if _array_is_trusted(array):return True
    trailing=max(1,int(np.prod(array.shape[1:],dtype=np.int64)))
    rows=max(1,_VALIDATION_CELLS_PER_CHUNK//trailing)
    result=all(bool(np.all(np.isfinite(array[start:start+rows])))
               for start in range(0,len(array),rows))
    if result:_trust_array(array)
    return result


def _unique_strings_bounded(value:np.ndarray)->bool:
    """Check exact string uniqueness without one corpus-wide ``tolist`` copy."""

    array=np.asarray(value,str)
    if _array_is_trusted(array):return True
    seen:set[str]=set();rows=65_536
    for start in range(0,len(array),rows):
        block=tuple(map(str,array[start:start+rows]))
        if len(block)!=len(set(block)) or any(item in seen for item in block):
            return False
        seen.update(block)
    _trust_array(array);return True


def _string_sequence_object_sha256(value:np.ndarray)->str:
    """Match ``object_sha256(tuple(strings))`` without materializing the tuple."""

    array=np.asarray(value,str);identity=id(array)
    cached=_STRING_SEQUENCE_DIGESTS.get(identity)
    if cached is not None and cached[0]() is array:return cached[1]
    digest=hashlib.sha256();digest.update(b"[")
    for index,item in enumerate(array):
        if index:digest.update(b",")
        digest.update(json.dumps(str(item),sort_keys=True,separators=(",",":"),
                                 allow_nan=False).encode("utf-8"))
    digest.update(b"]\n");result=digest.hexdigest()
    try:
        def discard(reference:weakref.ReferenceType[object],*,key:int=identity)->None:
            if (_STRING_SEQUENCE_DIGESTS.get(key) is not None
                    and _STRING_SEQUENCE_DIGESTS[key][0] is reference):
                _STRING_SEQUENCE_DIGESTS.pop(key,None)
        reference=weakref.ref(array,discard)
        _STRING_SEQUENCE_DIGESTS[identity]=(reference,result)
    except TypeError:
        pass
    return result


class _StoredComponentTrainingMatrix(ComponentTrainingMatrix):
    """Strict-loaded component matrix with bounded, reusable X validation."""

    __slots__=()

    def validate(self)->None:
        names=validate_model_feature_names(self.feature_names)
        matrix=np.asarray(self.x);n=len(matrix)
        fields=tuple(getattr(self,name) for name in (
            "opportunity_id","series_id","asset","day","current_asinh",
            "continuation_asinh","continuation_observed","wall_target",
            "adverse_usd","occupancy_sec","sample_weight"))
        x_valid=_array_is_trusted(self.x)
        if (matrix.ndim!=2 or matrix.shape[1]!=len(names) or n==0
                or any(np.asarray(value).shape!=(n,) for value in fields)
                or (not x_valid and not _all_finite_bounded(matrix))
                or not _all_finite_bounded(self.current_asinh)
                or not _all_finite_bounded(self.continuation_asinh)
                or not np.all(np.isin(self.wall_target,(0,1)))
                or np.any(np.asarray(self.adverse_usd)<0)
                or np.any(np.asarray(self.occupancy_sec)<0)
                or np.any(np.asarray(self.sample_weight)<=0)
                or not np.all(np.isin(self.asset,C.ASSETS))
                or not _unique_strings_bounded(self.opportunity_id)
                or len(self.source_receipts)!=len(np.unique(self.day))
                or any(not _sha(value) for value in self.source_receipts)):
            raise RecoveryRefusal("component training matrix is malformed")
        if not x_valid:_trust_array(self.x)
        for trading_day in np.unique(self.day):C.guard_date(int(trading_day))

    @property
    def receipt_sha256(self)->str:
        self.validate();days=tuple(map(int,np.unique(self.day)))
        return C.object_sha256({
            "schema":"QRE2TABCOMPONENTMATRIX2","features":self.feature_names,
            "rows":len(self.x),"days":days,
            "ids_sha256":_string_sequence_object_sha256(self.opportunity_id),
            "day_sources":tuple(zip(days,self.source_receipts)),
        })


class _StoredActionTrainingMatrix(ActionTrainingMatrix):
    """Strict-loaded action matrix with bounded, reusable X validation."""

    __slots__=()

    def validate(self)->None:
        matrix=np.asarray(self.x);n=len(matrix);x_valid=_array_is_trusted(self.x)
        if (not self.feature_names
                or len(self.feature_names)!=len(set(self.feature_names))
                or matrix.ndim!=2 or matrix.shape[1]!=len(self.feature_names)
                or n==0 or (not x_valid and not _all_finite_bounded(matrix))
                or np.asarray(self.regret_log_target).shape!=(n,3)
                or np.asarray(self.regret_cents).shape!=(n,3)
                or not _all_finite_bounded(self.regret_log_target)
                or np.any(np.asarray(self.regret_log_target)<0)
                or np.any(np.asarray(self.regret_cents)<0)
                or any(np.asarray(getattr(self,name)).shape!=(n,) for name in (
                    "opportunity_id","series_id","asset","day",
                    "optimal_action","action_margin_cents","sample_weight"))
                or not np.all(np.isin(self.asset,C.ASSETS))
                or not np.all(np.isin(self.optimal_action,POLICY_ACTIONS))
                or np.any(np.asarray(self.action_margin_cents)<0)
                or np.any(np.asarray(self.sample_weight)<=0)
                or not _sha(self.component_oof_receipt_sha256)
                or len(self.source_receipts)!=len(np.unique(self.day))
                or any(not _sha(value) for value in self.source_receipts)
                or self.forced_occupied_rows_omitted<0):
            raise RecoveryRefusal("action training matrix is malformed")
        if not x_valid:_trust_array(self.x)
        scale=VALUE_SCALE_USD*100.0;rows=262_144
        for start in range(0,n,rows):
            stop=min(n,start+rows)
            expected=np.log1p(np.asarray(
                self.regret_cents[start:stop],np.float64)/scale)
            if not np.allclose(expected,self.regret_log_target[start:stop],
                               atol=1e-12,rtol=0):
                raise RecoveryRefusal("action regret transform differs")
        for trading_day in np.unique(self.day):C.guard_date(int(trading_day))


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _manifest(path:Path,schema:str)->Mapping[str,object]:
    try:value=json.loads(path.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot read tabular matrix manifest") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if value.get("schema")!=schema or C.object_sha256(core)!=value.get("receipt_sha256"):
        raise RecoveryRefusal("tabular matrix manifest receipt differs")
    return MappingProxyType(value)


def _close_memmap_values(values:Sequence[np.ndarray])->None:
    closed:set[int]=set()
    for value in values:
        mapping=getattr(value,"_mmap",None)
        if mapping is not None and id(mapping) not in closed:
            mapping.close();closed.add(id(mapping))


def _save_arrays(stage:Path,matrix:object,names:tuple[str,...])->Mapping[str,str]:
    hashes={}
    for name in names:
        path=stage/f"{name}.npy"
        with path.open("xb") as handle:
            np.save(handle,np.asarray(getattr(matrix,name)),allow_pickle=False)
            handle.flush();os.fsync(handle.fileno())
        hashes[path.name]=C.file_sha256(path)
    return MappingProxyType(hashes)


def _atomic_directory(target:Path,writer)->str:
    target=C.assert_workspace_output(target)
    if target.exists():raise RecoveryRefusal("tabular matrix store already exists")
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
    try:
        writer(stage)
        for child in stage.iterdir():
            if child.is_file():
                with child.open("rb") as handle:os.fsync(handle.fileno())
        descriptor=os.open(stage,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        os.replace(stage,target)
        descriptor=os.open(target.parent,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    except Exception:
        shutil.rmtree(stage,ignore_errors=True);raise
    return C.file_sha256(target/"manifest.json")


def save_component_matrix(matrix:ComponentTrainingMatrix,
                          path:os.PathLike[str]|str)->str:
    matrix.validate()
    def writer(stage:Path)->None:
        hashes=_save_arrays(stage,matrix,_COMPONENT_ARRAYS)
        core={"schema":COMPONENT_STORE_SCHEMA,"feature_names":matrix.feature_names,
              "source_receipts":matrix.source_receipts,
              "matrix_receipt_sha256":matrix.receipt_sha256,
              "rows":len(matrix.x),"columns":len(matrix.feature_names),
              "files":dict(hashes),"numpy_version":np.__version__,
              "strict_reload":True,"h2_open_count":0}
        C.atomic_json(stage/"manifest.json",{**core,"receipt_sha256":C.object_sha256(core)})
    return _atomic_directory(Path(path),writer)


def load_component_matrix(path:os.PathLike[str]|str)->ComponentTrainingMatrix:
    source=Path(path).resolve();C.guard_payload(source)
    manifest=_manifest(source/"manifest.json",COMPONENT_STORE_SCHEMA)
    arrays={}
    try:
        for name in _COMPONENT_ARRAYS:
            file=source/f"{name}.npy"
            if C.file_sha256(file)!=manifest["files"].get(file.name):
                raise RecoveryRefusal(f"component matrix file differs: {name}")
            arrays[name]=np.load(file,allow_pickle=False,mmap_mode="r")
        result=_StoredComponentTrainingMatrix(
            feature_names=tuple(manifest["feature_names"]),
            source_receipts=tuple(manifest["source_receipts"]),**arrays)
        result.validate()
        if result.receipt_sha256!=manifest["matrix_receipt_sha256"]:
            raise RecoveryRefusal("component matrix identity differs after reload")
        return result
    except Exception:
        _close_memmap_values(tuple(arrays.values()));raise


def save_action_matrix(matrix:ActionTrainingMatrix,
                       path:os.PathLike[str]|str)->str:
    matrix.validate()
    def writer(stage:Path)->None:
        hashes=_save_arrays(stage,matrix,_ACTION_ARRAYS)
        core={"schema":ACTION_STORE_SCHEMA,"feature_names":matrix.feature_names,
              "component_oof_receipt_sha256":matrix.component_oof_receipt_sha256,
              "source_receipts":matrix.source_receipts,
              "forced_occupied_rows_omitted":matrix.forced_occupied_rows_omitted,
              "matrix_receipt_sha256":matrix.receipt_sha256,
              "rows":len(matrix.x),"columns":len(matrix.feature_names),
              "files":dict(hashes),"numpy_version":np.__version__,
              "strict_reload":True,"h2_open_count":0}
        C.atomic_json(stage/"manifest.json",{**core,"receipt_sha256":C.object_sha256(core)})
    return _atomic_directory(Path(path),writer)


def load_action_matrix(path:os.PathLike[str]|str)->ActionTrainingMatrix:
    source=Path(path).resolve();C.guard_payload(source)
    manifest=_manifest(source/"manifest.json",ACTION_STORE_SCHEMA)
    arrays={}
    try:
        for name in _ACTION_ARRAYS:
            file=source/f"{name}.npy"
            if C.file_sha256(file)!=manifest["files"].get(file.name):
                raise RecoveryRefusal(f"action matrix file differs: {name}")
            arrays[name]=np.load(file,allow_pickle=False,mmap_mode="r")
        result=_StoredActionTrainingMatrix(
            feature_names=tuple(manifest["feature_names"]),
            component_oof_receipt_sha256=manifest["component_oof_receipt_sha256"],
            source_receipts=tuple(manifest["source_receipts"]),
            forced_occupied_rows_omitted=int(
                manifest["forced_occupied_rows_omitted"]),**arrays)
        result.validate()
        if result.receipt_sha256!=manifest["matrix_receipt_sha256"]:
            raise RecoveryRefusal("action matrix identity differs after reload")
        return result
    except Exception:
        _close_memmap_values(tuple(arrays.values()));raise


def _day_from_path(path:os.PathLike[str]|str)->int:
    values=C.dates_in_basename(path)
    if len(values)!=1:
        raise RecoveryRefusal("training shard path has no unique day")
    C.guard_date(values[0]);return int(values[0])


def _paths_by_day(paths:Sequence[os.PathLike[str]|str])->Mapping[int,tuple[Path,...]]:
    output:dict[int,list[Path]]={}
    for raw in paths:
        path=Path(raw).resolve();C.guard_payload(path)
        output.setdefault(_day_from_path(path),[]).append(path)
    return MappingProxyType({day:tuple(sorted(rows))
                              for day,rows in sorted(output.items())})


def _npz_stored_identity(path:Path,*,schema:str,day_key:str)->tuple[str,int]:
    """Read source identity metadata without inflating the feature matrix."""

    C.guard_payload(path)
    try:
        with np.load(path,allow_pickle=False) as values:
            if str(values["schema"][0])!=schema:
                raise RecoveryRefusal("day-join source schema differs")
            representation=str(values["representation_sha256"][0])
            days=np.unique(values[day_key].astype(np.int64,copy=False))
    except (OSError,ValueError,KeyError) as exc:
        raise RecoveryRefusal("cannot read day-join source identity") from exc
    if not _sha(representation) or len(days)!=1:
        raise RecoveryRefusal("day-join source identity is malformed")
    day=int(days[0]);C.guard_date(day);return representation,day


def _load_or_projected_feature(path:Path,schema:CausalFeatureSchema
                               )->tuple[str,CausalFeatureShard|None]:
    """Cache the exact projected representation used in day-store identities."""

    source_representation,day=_npz_stored_identity(
        path,schema=FEATURE_SHARD_SCHEMA,day_key="day")
    implementation=C.file_sha256(
        Path(__file__).with_name("tabular_delayed_corpus.py"))
    identity=C.object_sha256({"schema":PROJECTION_RECEIPT_SCHEMA,
        "source":source_representation,"feature_schema":schema.receipt_sha256,
        "implementation":implementation})
    target=C.CACHE_ROOT/"feature_projection_receipts"/identity/"receipt.json"
    projected=None
    if not target.is_file():
        source=CausalFeatureShard.load(path)
        if source.representation_sha256!=source_representation:
            raise RecoveryRefusal("feature source changed during projection")
        projected=project_feature_schema(source,schema)
        core={"schema":PROJECTION_RECEIPT_SCHEMA,
            "identity_sha256":identity,"source":source_representation,
            "day":day,"feature_schema":schema.receipt_sha256,
            "projected":projected.representation_sha256,
            "implementation":implementation,"h2_open_count":0}
        C.atomic_json(target,{**core,"receipt_sha256":C.object_sha256(core)})
    value=_manifest(target,PROJECTION_RECEIPT_SCHEMA)
    if (value.get("identity_sha256")!=identity
            or value.get("source")!=source_representation
            or int(value.get("day",-1))!=day
            or value.get("feature_schema")!=schema.receipt_sha256
            or value.get("implementation")!=implementation
            or not _sha(value.get("projected"))
            or value.get("h2_open_count")!=0):
        raise RecoveryRefusal("feature projection receipt differs")
    if (projected is not None
            and projected.representation_sha256!=value["projected"]):
        raise RecoveryRefusal("published feature projection receipt differs")
    return str(value["projected"]),projected


def _projected_feature(path:Path,schema:CausalFeatureSchema,
                       expected_representation:str)->CausalFeatureShard:
    result=project_feature_schema(CausalFeatureShard.load(path),schema)
    if result.representation_sha256!=expected_representation:
        raise RecoveryRefusal("feature projection changed after receipt")
    return result


def materialize_component_day_stores(*,
        feature_paths:Sequence[os.PathLike[str]|str],
        teacher_paths:Sequence[os.PathLike[str]|str],
        feature_schema:CausalFeatureSchema,output_root:os.PathLike[str]|str,
        )->tuple[Path,...]:
    """Build restartable one-day joins before any corpus-wide allocation."""

    feature_schema.__post_init__();features=_paths_by_day(feature_paths)
    teachers=_paths_by_day(teacher_paths)
    if set(features)!=set(teachers) or any(len(rows)!=1 for rows in teachers.values()):
        raise RecoveryRefusal("component day-store feature/teacher roster differs")
    root=C.assert_workspace_output(output_root);output=[]
    implementation=C.file_sha256(Path(__file__).with_name("tabular_training.py"))
    schema_receipt=feature_schema.receipt_sha256
    for day in sorted(features):
        projected=tuple(_load_or_projected_feature(path,feature_schema)
                        for path in features[day])
        sources=tuple(row[0] for row in projected)
        teacher_representation,teacher_day=_npz_stored_identity(
            teachers[day][0],schema=TEACHER_DAY_SCHEMA,day_key="trading_day")
        if teacher_day!=day:raise RecoveryRefusal("component teacher day drifts")
        identity=C.object_sha256({"schema":DAY_STORE_INDEX_SCHEMA,
            "kind":"COMPONENT","day":day,"feature_schema":schema_receipt,
            "features":sources,"teacher":teacher_representation,
            "implementation":implementation})
        target=root/"component_days"/identity
        expected=C.object_sha256({"schema":"QRE2TABCOMPONENTDAYSOURCE1",
            "day":day,"teacher":teacher_representation,"features":sources})
        if target.is_dir():
            manifest=_manifest(target/"manifest.json",COMPONENT_STORE_SCHEMA)
            if (tuple(manifest.get("feature_names",()))!=feature_schema.names
                    or tuple(manifest.get("source_receipts",()))!=(expected,)
                    or int(manifest.get("columns",-1))!=len(feature_schema.names)
                    or int(manifest.get("rows",0))<=0):
                raise RecoveryRefusal("component day-store resume manifest differs")
            output.append(target);continue
        else:
            feature_rows=tuple(row if row is not None else
                _projected_feature(path,feature_schema,receipt)
                for path,(receipt,row) in zip(features[day],projected))
            teacher=ExactDelayedTeacherDay.load(teachers[day][0])
            if teacher.representation_sha256!=teacher_representation:
                raise RecoveryRefusal("component teacher changed after identity")
            matrix=assemble_component_training_matrix(feature_rows,(teacher,))
            save_component_matrix(matrix,target);matrix=load_component_matrix(target)
        try:
            if (tuple(np.unique(matrix.day))!=(day,)
                    or matrix.feature_names!=feature_schema.names
                    or matrix.source_receipts!=(expected,)):
                raise RecoveryRefusal("component day-store strict resume differs")
        finally:_close_matrix_memmaps(matrix,_COMPONENT_ARRAYS)
        output.append(target)
    return tuple(output)


def _component_oof_day(table:ComponentPredictionTable,day:int)->ComponentPredictionTable:
    table.validate();keep=np.asarray(table.day,np.int64)==int(day)
    if not keep.any():raise RecoveryRefusal("action day lacks component OOF rows")
    result=ComponentPredictionTable(
        np.asarray(table.opportunity_id)[keep],np.asarray(table.day)[keep],
        np.asarray(table.values)[keep],
        np.asarray(table.fold_model_receipt_sha256)[keep],
        np.asarray(table.fold_information_max_day)[keep],
        table.source_feature_receipts,table.prediction_names,
        table.model_receipt_sha256,
        table.chronology_receipt_sha256,True)
    result.validate();return result


def materialize_action_day_stores(*,
        feature_paths:Sequence[os.PathLike[str]|str],
        teacher_paths:Sequence[os.PathLike[str]|str],
        component_oof:ComponentPredictionTable,
        feature_schema:CausalFeatureSchema,output_root:os.PathLike[str]|str,
        )->tuple[Path,...]:
    """Build one-day portfolio-action joins using the matching OOF stack."""

    feature_schema.__post_init__();component_oof.validate()
    features=_paths_by_day(feature_paths);teachers=_paths_by_day(teacher_paths)
    eligible=set(map(int,np.unique(component_oof.day)))
    days=sorted(set(features)&set(teachers)&eligible)
    if not days or any(len(teachers[day])!=1 for day in days):
        raise RecoveryRefusal("action day-store roster is empty/malformed")
    root=C.assert_workspace_output(output_root);output=[]
    implementation=C.file_sha256(Path(__file__).with_name("tabular_training.py"))
    schema_receipt=feature_schema.receipt_sha256
    component_oof_receipt=component_oof.receipt_sha256
    for day in days:
        projected=tuple(_load_or_projected_feature(path,feature_schema)
                        for path in features[day])
        sources=tuple(row[0] for row in projected)
        teacher_representation,teacher_day=_npz_stored_identity(
            teachers[day][0],schema=TEACHER_DAY_SCHEMA,day_key="trading_day")
        if teacher_day!=day:raise RecoveryRefusal("action teacher day drifts")
        identity=C.object_sha256({"schema":DAY_STORE_INDEX_SCHEMA,
            "kind":"ACTION","day":day,"feature_schema":schema_receipt,
            "features":sources,"teacher":teacher_representation,
            "component_oof":component_oof_receipt,
            "implementation":implementation})
        target=root/"action_days"/identity
        source=C.object_sha256({"schema":"QRE2TABACTIONDAYSOURCE1",
            "day":day,"teacher":teacher_representation,
            "features":sources,"component_oof":component_oof_receipt})
        action_names=feature_schema.names+COMPONENT_STACK_NAMES+tuple(
            ACTION_STATE_FEATURE_NAMES)
        if target.is_dir():
            manifest=_manifest(target/"manifest.json",ACTION_STORE_SCHEMA)
            if (tuple(manifest.get("feature_names",()))!=action_names
                    or tuple(manifest.get("source_receipts",()))!=(source,)
                    or manifest.get("component_oof_receipt_sha256")
                       !=component_oof_receipt
                    or int(manifest.get("columns",-1))!=len(action_names)
                    or int(manifest.get("rows",0))<=0):
                raise RecoveryRefusal("action day-store resume manifest differs")
            output.append(target);continue
        else:
            feature_rows=tuple(row if row is not None else
                _projected_feature(path,feature_schema,receipt)
                for path,(receipt,row) in zip(features[day],projected))
            teacher=ExactDelayedTeacherDay.load(teachers[day][0])
            if teacher.representation_sha256!=teacher_representation:
                raise RecoveryRefusal("action teacher changed after identity")
            if not len(teacher.action_opportunity_id):continue
            local_oof=_component_oof_day(component_oof,day)
            try:
                matrix=assemble_action_training_matrix(
                    feature_rows,(teacher,),local_oof)
            except RecoveryRefusal as exc:
                if str(exc)!="no free-asset action state survived the exact join":raise
                continue
            matrix=replace(matrix,
                component_oof_receipt_sha256=component_oof_receipt,
                source_receipts=(source,))
            matrix.validate();save_action_matrix(matrix,target)
            matrix=load_action_matrix(target)
        try:
            if (tuple(np.unique(matrix.day))!=(day,)
                    or matrix.component_oof_receipt_sha256
                       !=component_oof_receipt):
                raise RecoveryRefusal("action day-store strict resume differs")
        finally:_close_matrix_memmaps(matrix,_ACTION_ARRAYS)
        output.append(target)
    if not output:raise RecoveryRefusal("action day stores contain no trainable rows")
    return tuple(output)


def _close_matrix_memmaps(matrix:object,names:Sequence[str])->None:
    """Close every independently loaded ``.npy`` mapping exactly once."""

    _close_memmap_values(tuple(getattr(matrix,name,None) for name in names))


def close_component_matrix(matrix:ComponentTrainingMatrix)->None:
    _close_matrix_memmaps(matrix,_COMPONENT_ARRAYS)


def close_action_matrix(matrix:ActionTrainingMatrix)->None:
    _close_matrix_memmaps(matrix,_ACTION_ARRAYS)


def _day_store_descriptors(paths:Sequence[os.PathLike[str]|str],*,
                           kind:str)->tuple[Mapping[str,object],...]:
    loaders={"COMPONENT":load_component_matrix,"ACTION":load_action_matrix}
    schemas={"COMPONENT":COMPONENT_STORE_SCHEMA,"ACTION":ACTION_STORE_SCHEMA}
    arrays={"COMPONENT":_COMPONENT_ARRAYS,"ACTION":_ACTION_ARRAYS}
    if kind not in loaders:raise RecoveryRefusal("unknown matrix descriptor kind")
    output=[]
    for raw in paths:
        path=Path(raw).resolve();matrix=loaders[kind](path)
        try:
            days=np.unique(np.asarray(matrix.day,np.int64))
            manifest=_manifest(path/"manifest.json",schemas[kind])
            layouts=tuple((name,np.asarray(getattr(matrix,name)).dtype.str,
                           tuple(np.asarray(getattr(matrix,name)).shape[1:]))
                          for name in arrays[kind])
            output.append(MappingProxyType({
                "path":str(path),"day":int(days[0]) if len(days)==1 else -1,
                "rows":len(matrix.x),"feature_names":matrix.feature_names,
                "source_receipt":matrix.source_receipts[0]
                    if len(matrix.source_receipts)==1 else "",
                "matrix_receipt_sha256":str(manifest["matrix_receipt_sha256"]),
                "layouts":layouts,
                "component_oof_receipt_sha256":getattr(
                    matrix,"component_oof_receipt_sha256",None),
            }))
        finally:_close_matrix_memmaps(matrix,arrays[kind])
    rows=tuple(sorted(output,key=lambda row:int(row["day"])))
    if not rows:raise RecoveryRefusal("matrix combine has no day stores")
    days=tuple(int(row["day"]) for row in rows)
    if (days!=tuple(sorted(set(days)))
            or any(row["feature_names"]!=rows[0]["feature_names"] for row in rows)
            or any(not row["source_receipt"] for row in rows)):
        raise RecoveryRefusal("matrix day stores overlap or drift")
    _canonical_layouts(rows)
    if kind=="ACTION" and any(row["component_oof_receipt_sha256"]
            !=rows[0]["component_oof_receipt_sha256"] for row in rows):
        raise RecoveryRefusal("action day stores use different component stacks")
    return rows


def _canonical_layouts(
        rows:Sequence[Mapping[str,object]])->tuple[tuple[str,str,tuple[int,...]],...]:
    """Promote lossless string widths while refusing real layout drift."""

    reference=tuple(rows[0]["layouts"]);output=[]
    for index,(name,dtype,trailing) in enumerate(reference):
        dtypes=[]
        for row in rows:
            layouts=tuple(row["layouts"])
            if len(layouts)!=len(reference):
                raise RecoveryRefusal("matrix day-store array roster drifts")
            local_name,local_dtype,local_trailing=layouts[index]
            if local_name!=name or tuple(local_trailing)!=tuple(trailing):
                raise RecoveryRefusal("matrix day-store array layout drifts")
            dtypes.append(np.dtype(local_dtype))
        kinds={value.kind for value in dtypes}
        if len(kinds)!=1:
            raise RecoveryRefusal("matrix day-store array dtype kind drifts")
        if kinds<= {"U"} or kinds<= {"S"}:
            promoted=np.result_type(*dtypes)
        elif len(set(dtypes))==1:
            promoted=dtypes[0]
        else:
            raise RecoveryRefusal("matrix day-store numeric dtype drifts")
        output.append((str(name),promoted.str,tuple(trailing)))
    return tuple(output)


def _combine_day_stores(paths:Sequence[os.PathLike[str]|str],target:Path,
                        *,kind:str,
                        descriptors:Sequence[Mapping[str,object]]|None=None)->str:
    loaders={"COMPONENT":load_component_matrix,"ACTION":load_action_matrix}
    schemas={"COMPONENT":COMPONENT_STORE_SCHEMA,"ACTION":ACTION_STORE_SCHEMA}
    arrays={"COMPONENT":_COMPONENT_ARRAYS,"ACTION":_ACTION_ARRAYS}
    if kind not in loaders:raise RecoveryRefusal("unknown matrix combine kind")
    rows=tuple(descriptors or _day_store_descriptors(paths,kind=kind))
    if not rows:raise RecoveryRefusal("matrix combine has no descriptors")
    total=sum(int(row["rows"]) for row in rows);day_count=len(rows)

    def writer(stage:Path)->None:
        mappings={}
        try:
            for name,dtype,trailing in _canonical_layouts(rows):
                mappings[name]=np.lib.format.open_memmap(
                    stage/f"{name}.npy",mode="w+",dtype=np.dtype(dtype),
                    shape=(total,*trailing))
            cursor=0;forced_occupied=0
            for descriptor in rows:
                row=loaders[kind](descriptor["path"])
                try:
                    if (len(row.x)!=int(descriptor["rows"])
                            or int(np.asarray(row.day,np.int64)[0])
                               !=int(descriptor["day"])):
                        raise RecoveryRefusal("day store changed during streamed combine")
                    end=cursor+len(row.x)
                    for name,mapping in mappings.items():
                        if name=="sample_weight":continue
                        mapping[cursor:end]=np.asarray(getattr(row,name))
                    if kind=="COMPONENT":
                        mappings["sample_weight"][cursor:end]=(
                            total/(day_count*len(row.x)))
                    else:
                        multiplier=1.0+np.minimum(
                            np.asarray(row.action_margin_cents,np.float64)
                            /(VALUE_SCALE_USD*100.0),9.0)
                        mappings["sample_weight"][cursor:end]=(multiplier
                            *(total/day_count)/float(multiplier.sum()))
                        forced_occupied+=int(row.forced_occupied_rows_omitted)
                    cursor=end
                finally:_close_matrix_memmaps(row,arrays[kind])
            for mapping in mappings.values():mapping.flush()
            common={"feature_names":tuple(rows[0]["feature_names"]),
                    "source_receipts":tuple(
                        str(row["source_receipt"]) for row in rows)}
            if kind=="COMPONENT":
                matrix=_StoredComponentTrainingMatrix(**common,
                    **{name:mappings[name] for name in _COMPONENT_ARRAYS})
                extra={}
            else:
                matrix=_StoredActionTrainingMatrix(**common,
                    component_oof_receipt_sha256=str(
                        rows[0]["component_oof_receipt_sha256"]),
                    forced_occupied_rows_omitted=forced_occupied,
                    **{name:mappings[name] for name in _ACTION_ARRAYS})
                extra={"component_oof_receipt_sha256":matrix.component_oof_receipt_sha256,
                       "forced_occupied_rows_omitted":matrix.forced_occupied_rows_omitted}
            matrix.validate();matrix_receipt=matrix.receipt_sha256
            hashes={f"{name}.npy":C.file_sha256(stage/f"{name}.npy")
                    for name in arrays[kind]}
            core={"schema":schemas[kind],"feature_names":matrix.feature_names,
                  "source_receipts":matrix.source_receipts,**extra,
                  "matrix_receipt_sha256":matrix_receipt,
                  "rows":len(matrix.x),"columns":len(matrix.feature_names),
                  "files":hashes,"numpy_version":np.__version__,
                  "strict_reload":True,"streamed_from_day_stores":True,
                  "bounded_open_day_stores":True,
                  "lossless_string_dtype_promotion":True,
                  "fsync_before_atomic_publish":True,
                  "day_store_receipts":tuple(
                      str(row["matrix_receipt_sha256"]) for row in rows),
                  "h2_open_count":0}
            C.atomic_json(stage/"manifest.json",{
                **core,"receipt_sha256":C.object_sha256(core)})
        finally:
            for mapping in mappings.values():
                raw=getattr(mapping,"_mmap",None)
                if raw is not None:raw.close()
    return _atomic_directory(target,writer)


def load_existing_component_matrix(path:os.PathLike[str]|str,*,
        feature_names:Sequence[str])->ComponentTrainingMatrix|None:
    """Resume a published combined component matrix; extra day-store
    generations on disk must not invalidate it."""

    target=Path(path)
    if not target.is_dir():
        return None
    matrix=load_component_matrix(target)
    if matrix.feature_names!=tuple(feature_names):
        close_component_matrix(matrix)
        raise RecoveryRefusal("resumed component matrix feature names differ")
    return matrix


def load_existing_action_matrix(path:os.PathLike[str]|str
                                )->ActionTrainingMatrix|None:
    """Resume a published combined action matrix without reminting day stores."""

    target=Path(path)
    if not target.is_dir():
        return None
    return load_action_matrix(target)


def combine_component_day_stores(paths:Sequence[os.PathLike[str]|str],
                                 path:os.PathLike[str]|str)->ComponentTrainingMatrix:
    target=Path(path);rows=_day_store_descriptors(paths,kind="COMPONENT")
    expected=tuple(str(row["matrix_receipt_sha256"]) for row in rows)
    if target.is_dir():
        manifest=_manifest(target/"manifest.json",COMPONENT_STORE_SCHEMA)
        if tuple(manifest.get("day_store_receipts",()))!=expected:
            raise RecoveryRefusal("resumed component matrix day stores differ")
    else:_combine_day_stores(paths,target,kind="COMPONENT",descriptors=rows)
    return load_component_matrix(target)


def combine_action_day_stores(paths:Sequence[os.PathLike[str]|str],
                              path:os.PathLike[str]|str)->ActionTrainingMatrix:
    target=Path(path);rows=_day_store_descriptors(paths,kind="ACTION")
    expected=tuple(str(row["matrix_receipt_sha256"]) for row in rows)
    if target.is_dir():
        manifest=_manifest(target/"manifest.json",ACTION_STORE_SCHEMA)
        if tuple(manifest.get("day_store_receipts",()))!=expected:
            raise RecoveryRefusal("resumed action matrix day stores differ")
    else:_combine_day_stores(paths,target,kind="ACTION",descriptors=rows)
    return load_action_matrix(target)


__all__=["ACTION_STORE_SCHEMA","COMPONENT_STORE_SCHEMA",
         "close_action_matrix","close_component_matrix",
         "combine_action_day_stores","combine_component_day_stores",
         "load_action_matrix","load_component_matrix",
         "load_existing_action_matrix","load_existing_component_matrix",
         "materialize_action_day_stores","materialize_component_day_stores",
         "save_action_matrix","save_component_matrix"]
