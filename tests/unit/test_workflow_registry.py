from pathlib import Path

import pytest
import yaml

from assethold.engine import engine


def _registered_workflows():
    registry = yaml.safe_load(Path("docs/registry/workflows.yaml").read_text())
    assert registry["schema_version"] == 1
    return registry["workflows"]


@pytest.mark.parametrize("workflow", _registered_workflows())
def test_registered_workflow_runs_and_produces_outputs(workflow):
    input_file = Path(workflow["input"])
    assert input_file.is_file()

    for output in workflow["outputs"]:
        output_file = Path(output)
        if output_file.exists():
            output_file.unlink()

    engine(str(input_file))

    for output in workflow["outputs"]:
        output_file = Path(output)
        assert output_file.is_file()
        assert output_file.stat().st_size > 0
