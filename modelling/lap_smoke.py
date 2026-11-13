"""Synthetic-only public API smoke demo. Writes only modelling/.test-work/."""
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import lap_model
from lap_synthetic import create_dataset, scenario_input


def run():
    workspace = Path(__file__).resolve().parent / '.test-work' / ('lap_smoke_'+uuid4().hex)
    data, labels = create_dataset(workspace / 'evidence')
    with patch.object(lap_model, 'ARTIFACTS', workspace / 'artifacts'):
        evaluation = lap_model.train_lap_model(data, labels)
        output = lap_model.predict_lap_time(scenario_input(workspace / 'evidence'))
        result = {'synthetic_only': True, 'production_artifact_created': False,
                  'workspace': str(workspace), 'prediction': json.loads(output.to_json(orient='records', date_format='iso'))[0],
                  'test_metrics': evaluation['test']['metrics']}
        (workspace / 'smoke_result.json').write_text(json.dumps(result, indent=2))
        return result


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
