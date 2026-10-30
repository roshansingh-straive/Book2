"""Uploaded photos must remain distinct from saved benchmark/sample results."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.main import app
from server.recognition import RecognitionError

client = TestClient(app)


@pytest.fixture(autouse=True)
def local_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr('server.uploads.UPLOADS_DIR', tmp_path)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    return tmp_path


def picture(format='PNG', orientation=None):
    image = Image.new('RGB', (80, 40), '#b2c6ef')
    buffer = io.BytesIO()
    options = {}
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        options['exif'] = exif
    image.save(buffer, format=format, **options)
    return buffer.getvalue()


def upload(raw=None, name='my-shelf.png'):
    return client.post('/api/uploads', params={'filename': name}, content=raw or picture(), headers={'Content-Type': 'application/octet-stream'})


@pytest.mark.parametrize('format', ['JPEG', 'PNG', 'WEBP'])
def test_valid_upload_returns_its_actual_photo_and_metadata(format):
    raw = picture(format)
    response = upload(raw, f'shelf.{format.lower()}')
    assert response.status_code == 201
    photo = response.json()
    assert len(photo['upload_id']) == 32
    assert (photo['width'], photo['height']) == (80, 40)
    assert photo['byte_size'] == len(raw)
    served = client.get(photo['photo_url'])
    assert served.status_code == 200
    assert served.content == raw
    assert served.headers['content-type'] == photo['media_type']
    assert served.headers['x-content-type-options'] == 'nosniff'
    assert client.get(f"/api/uploads/{photo['upload_id']}").json() == photo


def test_uploaded_exif_dimensions_match_the_browser():
    response = upload(picture('JPEG', orientation=6), 'portrait.jpg')
    assert response.status_code == 201
    assert (response.json()['width'], response.json()['height']) == (40, 80)


def test_filenames_cannot_control_storage_paths(local_uploads):
    photo = upload(name='../nested\\my-shelf.png\r\n').json()
    assert photo['filename'] == 'my-shelf.png'
    assert (local_uploads / photo['upload_id'] / 'image').is_file()
    assert len(list(local_uploads.iterdir())) == 1


@pytest.mark.parametrize('raw', [b'not an image', b'<svg><script>bad()</script></svg>', picture('GIF')])
def test_image_bytes_are_validated_instead_of_trusting_the_filename(raw, local_uploads):
    response = upload(raw, 'fake-photo.png')
    assert response.status_code == 422
    assert not list(local_uploads.iterdir())


def test_upload_size_limit_is_enforced_before_saving(monkeypatch, local_uploads):
    monkeypatch.setattr('server.main.MAX_IMAGE_BYTES', 8)
    response = upload(b'123456789')
    assert response.status_code == 413
    assert not list(local_uploads.iterdir())


def test_unknown_photo_and_invalid_ids_are_not_replayed():
    for path in ['/api/uploads/not-a-valid-id', f"/api/uploads/{'a'*32}/image", f"/api/uploads/{'a'*32}/analysis/bay_f3"]:
        assert client.get(path).status_code == 404


def test_upload_cannot_use_a_saved_sample_result():
    photo = upload().json()
    response = client.post('/api/scan/stream', json={'bay_id': 'bay_f3', 'upload_id': photo['upload_id'], 'mode': 'replay'})
    assert response.status_code == 422
    assert 'Sample results cannot be used' in response.json()['detail']
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f3").json() == {'result': None}


def test_unavailable_live_service_keeps_upload_without_claiming_results():
    photo = upload().json()
    response = client.post('/api/scan/stream', json={'bay_id': 'bay_f3', 'upload_id': photo['upload_id'], 'mode': 'live'})
    assert response.status_code == 401
    assert client.get(photo['photo_url']).status_code == 200
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f3").json() == {'result': None}
    assert client.get('/api/health').json()['upload_analysis_available']


def test_personal_provider_key_does_not_replace_foundry_session(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    photo = upload().json()
    response = client.post('/api/scan/stream', json={'bay_id': 'bay_a1', 'upload_id': photo['upload_id'], 'mode': 'live'})
    assert response.status_code == 401
    health = client.get('/api/health').json()
    assert health['live_available_by_difficulty']['easy']
    assert health['upload_analysis_available']


def test_analysis_reads_uploaded_bytes_and_persists_result_for_refresh(monkeypatch):
    raw = picture()
    photo = upload(raw, 'actual-upload.png').json()
    calls = []
    async def recognize(image, profile, emit, token):
        calls.append((image, profile, token))
        await emit({'step': 1, 'status': 'reading'})
        return [], {'mode': 'live', 'model': profile.name, 'effort': 'high', 'run_id': 'test-run'}
    monkeypatch.setattr('server.main.run_recognition', recognize)
    token = 'ephemeral-test-token'
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post('/api/scan/stream', json={'bay_id': 'bay_a1', 'upload_id': photo['upload_id'], 'mode': 'live'}, headers=headers)
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert [event['status'] for event in events] == ['reading', 'comparing', 'complete']
    result = events[-1]['result']
    assert calls[0][0] == raw
    assert calls[0][1].model_id == 'gemini-3.1-pro-preview'
    assert calls[0][2] == token
    assert result['upload_id'] == photo['upload_id']
    assert result['source_kind'] == 'upload'
    assert result['photo_url'] == photo['photo_url']
    assert result['photo_filename'] == 'actual-upload.png'
    assert result['shelf_items'] == []
    assert result['metrics']['matched_count'] == 0
    assert token not in json.dumps(result)
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_a1").json()['result'] == result
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f3").json()['result'] is None
    # A later failed rescan must leave the completed analysis intact.
    async def fail(*args):
        raise RecognitionError('Provider unavailable')
    monkeypatch.setattr('server.main.run_recognition', fail)
    failed = client.post('/api/scan/stream', json={'bay_id': 'bay_a1', 'upload_id': photo['upload_id'], 'mode': 'live'}, headers=headers)
    assert '"status": "error"' in failed.text
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_a1").json()['result'] == result


def test_saved_result_recompares_without_new_inference_and_preserves_photo(monkeypatch):
    from server.uploads import save_analysis
    from server.main import get_store
    from server.comparison import compare_books
    photo = upload().json()
    store = get_store()
    m1 = next(b for b in store['bays'] if b['id'] == 'bay_m1')
    titles = ['Before I Go to Sleep', 'Speaking for Myself', 'Brilliance of the Moon']
    books = [{'title': title, 'author': None, 'title_status': 'agreed', 'verification_status': 'needs_review',
              'position_status': 'needs_review', 'review_reasons': ['position_unconfirmed'], 'box': None} for title in titles]
    saved = {'upload_id': photo['upload_id'], 'photo_url': photo['photo_url'], 'photo_filename': photo['filename'],
             'bay_id': 'bay_m1', 'source_kind': 'upload', 'mode': 'live', 'run_id': 'original-paid-run',
             **compare_books(store, m1, books)}
    save_analysis(photo['upload_id'], 'bay_m1', saved)
    async def must_not_call(*args):
        raise AssertionError('Changing the comparison shelf must not call inference')
    monkeypatch.setattr('server.main.run_recognition', must_not_call)
    response = client.post(f"/api/uploads/{photo['upload_id']}/recompare", json={
        'source_bay_id': 'bay_m1', 'target_bay_id': 'bay_f1'})
    assert response.status_code == 200
    result = response.json()['result']
    assert result['run_id'] == 'original-paid-run'
    assert result['photo_url'] == photo['photo_url']
    assert result['bay_id'] == 'bay_f1'
    assert result['comparison_suggestion'] is None
    assert all(item['status'] == 'matched' for item in result['shelf_items'])
    assert not set(titles) & {item['title'] for item in result['missing_items']}
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result'] == result
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_m1").json()['result'] == saved


def test_previous_saved_box_review_is_migrated_without_another_scan(monkeypatch):
    from server.uploads import save_analysis
    photo = upload().json()
    entry = {'title': 'Before I Go to Sleep', 'author': None, 'verification_status': 'needs_review',
             'evidence': [{'tile_id': 'tile-1', 'pass': phase, 'visible_text': 'BEFORE I GO TO SLEEP',
                           'uncertain': False, 'box': {'top': top, 'left': .1, 'width': .3, 'height': .1}}
                          for phase, top in [('read', .1), ('verify', .5)]]}
    save_analysis(photo['upload_id'], 'bay_f1', {'upload_id': photo['upload_id'], 'photo_url': photo['photo_url'],
        'shelf_items': [entry], 'run_id': 'old-run', 'mode': 'live', 'source_kind': 'upload'})
    async def must_not_call(*args):
        raise AssertionError('Migration must not call inference')
    monkeypatch.setattr('server.main.run_recognition', must_not_call)
    result = client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result']
    assert result['comparison_version'] == 5
    assert result['shelf_items'][0]['status'] == 'matched'
    assert result['shelf_items'][0]['position_status'] == 'needs_review'
    assert all(item['title'] != 'Before I Go to Sleep' for item in result['missing_items'])
    assert result['run_id'] == 'old-run'
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result'] == result


def test_recomparison_requires_a_real_completed_result():
    photo = upload().json()
    path = f"/api/uploads/{photo['upload_id']}/recompare"
    assert client.post(path, json={'source_bay_id': 'bay_m1', 'target_bay_id': 'bay_f1'}).status_code == 409
    assert client.post(path, json={'source_bay_id': 'bay_m1', 'target_bay_id': 'bay_fake'}).status_code == 404
    assert client.post(path, json={'source_bay_id': '../escape', 'target_bay_id': 'bay_f1'}).status_code == 422
    assert client.post(path, json={'source_bay_id': 'bay_m1', 'target_bay_id': 'bay_f1', 'token': 'not-accepted'}).status_code == 422


@pytest.mark.parametrize('name', ['d.jpg', 'e.jpg', 'f.jpg'])
def test_original_apple_jpeg_primary_frame_is_a_valid_upload(name):
    from pathlib import Path
    raw = (Path(__file__).resolve().parents[1] / 'app/public/photos' / name).read_bytes()
    response = upload(raw, name)
    assert response.status_code == 201
    metadata = response.json()
    assert metadata['media_type'] == 'image/jpeg'
    assert metadata['width'] * metadata['height'] == 5712 * 4284
    assert client.get(metadata['photo_url']).content == raw


def test_version_three_result_reparses_matching_audit_without_inference(tmp_path, monkeypatch):
    import hashlib
    from server.uploads import save_analysis
    raw = picture()
    photo = upload(raw).json()
    run_id = 'b' * 32
    audit_dir = tmp_path / 'audits'
    audit_dir.mkdir()
    monkeypatch.setattr('server.main.RUNS_DIR', audit_dir)
    calls = []
    for phase, title, size in [('read', 'Speaking for Myself: the autobiography', [80,40]), ('verify', 'Speaking for Myself', [40,80])]:
        calls.append({'tile_id':'tile-1','pass':phase,'image_size':size,'complete':True,
                      'response_text':json.dumps({'books':[{'title':title,'author':'Cherie Blair',
                          'visible_text':title,'uncertain':False,'box':None}]})})
    audit = {'run_id':run_id,'image_sha256':hashlib.sha256(raw).hexdigest(),'image_size':[80,40],
             'status':'complete','tiles':[{'id':'tile-1','bounds':[0,0,80,40]}], 'calls':calls}
    path = audit_dir / f'{run_id}.json'
    path.write_text(json.dumps(audit))
    original_audit = path.read_bytes()
    save_analysis(photo['upload_id'], 'bay_f1', {'comparison_version':3,'run_id':run_id,
        'upload_id':photo['upload_id'],'photo_url':photo['photo_url'],'mode':'live', 'shelf_items':[]})
    async def no_inference(*args):
        raise AssertionError('A saved result must be reprocessed without inference')
    monkeypatch.setattr('server.main.run_recognition', no_inference)
    result = client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result']
    assert result['comparison_version'] == 5
    assert result['shelf_items'][0]['title'] == 'Speaking for Myself'
    assert result['shelf_items'][0]['status'] == 'matched'
    assert result['shelf_items'][0]['title_status'] == 'agreed'
    assert result['metrics']['location_review_count'] == 1
    assert not any(item['title']=='Speaking for Myself' for item in result['missing_items'])
    assert path.read_bytes() == original_audit
    def must_not_reparse(*args):
        raise AssertionError('An upgraded result should be cached')
    monkeypatch.setattr('server.main.reprocess_audit', must_not_reparse)
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result'] == result
    assert client.post(f"/api/uploads/{photo['upload_id']}/recompare", json={'source_bay_id':'bay_f1','target_bay_id':'bay_m1'}).status_code == 200
