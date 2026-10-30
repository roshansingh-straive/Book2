"""A single-pass scan must not rotate, reread or imply independent verification."""
import asyncio
import base64
import io
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from server.accuracy import FOUNDRY_GEMINI
from server.main import app, get_store
from server.comparison import compare_books
from server.recognition import run_recognition, reprocess_audit

ROOT = Path(__file__).resolve().parents[1]


def image_bytes(size=(120,60)):
    buffer = io.BytesIO()
    Image.new('RGB',size,'white').save(buffer,format='PNG')
    return buffer.getvalue()


def reply():
    payload={'modelVersion':FOUNDRY_GEMINI.model_id,'candidates':[{'content':{'parts':[{'text':json.dumps({
        'coordinate_system':'yxyx_1000','books':[{'title':'Leading','author':'Alex Ferguson',
        'visible_text':'LEADING ALEX FERGUSON','uncertain':False,'box_2d':[100,200,200,700]}],
    })}]},'finishReason':'STOP'}], 'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':10}}
    return httpx.Response(200,content=f'data: {json.dumps(payload)}\n\n'.encode())


def test_default_reads_once_without_transposing_and_does_not_claim_verification(tmp_path,monkeypatch):
    monkeypatch.setattr('server.recognition.RUNS_DIR',tmp_path)
    shapes=[]; events=[]
    def handler(request):
        body=json.loads(request.content)
        image=Image.open(io.BytesIO(base64.b64decode(body['contents'][0]['parts'][0]['inlineData']['data'])))
        shapes.append(image.size)
        assert 'Independently re-read' not in body['contents'][0]['parts'][1]['text']
        return reply()
    async def emit(event): events.append(event)
    books,metadata=asyncio.run(run_recognition(image_bytes(),FOUNDRY_GEMINI,emit,'test-token',transport=httpx.MockTransport(handler)))
    assert shapes==[(120,60)]
    assert metadata['harness']['calls_completed']==1
    assert metadata['harness']['rotated_verification'] is False
    assert metadata['reading_mode']=='single_pass'
    assert books[0]['title_status']=='single_read'
    assert books[0]['verification_status']=='single_pass'
    assert books[0]['position_status']=='estimated'
    assert all(event['status']!='verifying' for event in events)
    assert events[0]['total_calls']==1
    audit=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert {call['pass'] for call in audit['calls']}=={'read'}
    assert {obs['pass'] for obs in audit['observations']}=={'read'}


def test_24mp_grid_makes_twenty_base_requests_not_forty(tmp_path,monkeypatch):
    monkeypatch.setattr('server.recognition.RUNS_DIR',tmp_path)
    monkeypatch.setattr('server.recognition.encode_image',lambda image:'test-only-image')
    calls=[]
    def handler(request): calls.append(request); return reply()
    async def emit(event): pass
    books,metadata=asyncio.run(run_recognition(image_bytes((4284,5712)),FOUNDRY_GEMINI,emit,'test-token',transport=httpx.MockTransport(handler)))
    assert len(calls)==20
    assert metadata['harness']['tile_count']==20
    assert metadata['harness']['calls_completed']==20
    assert all(book['title_status']!='agreed' for book in books)


def test_single_pass_catalogue_matches_are_explicitly_not_independently_verified():
    fixture=json.loads((ROOT/'qa/fixtures/live_e_replies.json').read_text())
    books=reprocess_audit(fixture['audit'],first_pass_only=True)
    assert all(book['reading_mode']=='single_pass' for book in books)
    assert all(e['pass']=='read' for book in books for e in book['evidence'])
    store=get_store(); bay=next(b for b in store['bays'] if b['id']=='bay_f1')
    result=compare_books(store,bay,books,reading_mode='single_pass')
    assert result['reading_mode']=='single_pass'
    assert result['metrics']['matched_count']==91
    assert result['metrics']['independent_verified_count']==0
    assert result['metrics']['missing_count']==19
    assert all(book['status_label']=='Catalogue matched' for book in result['shelf_items'] if book['status']=='matched')
    assert not any(task['type']=='record_error' for task in result['action_tasks'])
    assert all('both readings' not in task['headline'] for task in result['action_tasks'])


def test_api_default_uses_one_reading_and_preserves_the_selected_policy(tmp_path,monkeypatch):
    monkeypatch.setattr('server.recognition.RUNS_DIR',tmp_path/'audits')
    monkeypatch.setattr('server.uploads.UPLOADS_DIR',tmp_path/'uploads')
    actual=run_recognition
    calls=[]
    def handler(request): calls.append(request); return reply()
    async def recognize(raw,profile,emit,token):
        return await actual(raw,profile,emit,token,transport=httpx.MockTransport(handler))
    monkeypatch.setattr('server.main.run_recognition',recognize)
    client=TestClient(app)
    photo=client.post('/api/uploads',content=image_bytes()).json()
    response=client.post('/api/scan/stream',json={'bay_id':'bay_f1','upload_id':photo['upload_id'],'mode':'live'},headers={'Authorization':'Bearer test-token'})
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    result=events[-1]['result']
    assert len(calls)==1
    assert result['reading_mode']=='single_pass'
    assert result['metrics']['matched_count']==1
    assert result['metrics']['independent_verified_count']==0
    assert client.get(f"/api/uploads/{photo['upload_id']}/analysis/bay_f1").json()['result']==result
    compared=client.post(f"/api/uploads/{photo['upload_id']}/recompare",json={'source_bay_id':'bay_f1','target_bay_id':'bay_m1'}).json()['result']
    assert compared['reading_mode']=='single_pass'
    assert len(calls)==1
