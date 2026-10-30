"""Regressions from the real supplied run, without company network/model calls."""
import json
from pathlib import Path

import pytest

from server.comparison import compare_books, title_score
from server.main import get_store
from server.recognition import Reading, merge_readings, parse_readings, provider_schema, reprocess_audit
from server.text import authors_compatible

ROOT = Path(__file__).resolve().parents[1]


def test_recorded_run_keeps_correct_titles_and_quarantines_non_book_text():
    fixture = json.loads((ROOT / 'qa/fixtures/live_e_replies.json').read_text())
    store = get_store()
    bay = next(b for b in store['bays'] if b['id'] == 'bay_f1')
    result = compare_books(store, bay, reprocess_audit(fixture['audit']))
    books = result['shelf_items']
    assert not any(book['title'].casefold() in {'john grisham', 'jack london', 'unknown title', 'p.d.james'} for book in books)
    assert any(book['exclusion_reason'] == 'author_only' for book in result['unresolved_readings'])
    speaking = [book for book in books if book['title'].casefold() == 'speaking for myself']
    assert len(speaking) == 1
    assert speaking[0]['status'] == 'matched'
    assert speaking[0]['title_status'] == 'agreed'
    assert len(speaking[0]['title_variants']) >= 2
    leading = next(book for book in books if book['title'] == 'Leading')
    assert leading['status'] == 'matched'
    digestion = next(book for book in books if book['title'].casefold() == 'disgusting digestion')
    assert digestion['status'] == 'matched'
    assert result['metrics']['matched_count'] >= fixture['baseline_metrics']['matched_count']
    assert result['metrics']['matched_count'] + result['metrics']['provisional_count'] + result['metrics']['missing_count'] == 110
    assert result['metrics']['review_count'] < fixture['baseline_metrics']['review_count']
    # These were genuinely not confirmed; the cleanup must not manufacture them.
    assert {'The Winner Stands Alone', 'Hunted', 'The Midnight Library'} <= {book['title'] for book in result['missing_items']}
    assert all(book['title'] not in {m['title'] for m in result['missing_items']} for book in books if book['status'] == 'matched')
    assert not any(task['type'] == 'recognition_review' and task['title'] == 'Before I Go to Sleep' for task in result['action_tasks'])
    assert result['metrics']['location_review_count'] > 0
    assert not any(book['title']=='Hundred Names' for book in books)
    assert any(book['title']=='Hundred Names' and book['exclusion_reason']=='possible_duplicate' for book in result['unresolved_readings'])
    original = next(book for book in books if book['title'].casefold()=='one hundred names')
    assert 'Hundred Names' in original['unconfirmed_variants']
    assert original['title_status']=='agreed'


@pytest.mark.parametrize('author,catalogue', [
    ('Alex Ferguson', 'Alex Ferguson with Michael Moritz'),
    ('केविन मिसल', 'केविन मिसल (Kevin Missal)'),
    ('Kevin Missal', 'केविन मिसल (Kevin Missal)'),
])
def test_coauthor_and_transliteration_aliases_do_not_veto_exact_title(author, catalogue):
    assert authors_compatible(author, catalogue)


def test_different_authors_and_distinct_volumes_still_require_caution():
    assert not authors_compatible('Cherie Blair', 'S.J. Watson')
    assert title_score('The Dark Tower Volume IV', 'The Dark Tower Volume V') == 0
    assert title_score('Star Wars Episode V', 'Star Wars Episode VI') == 0
    assert title_score('Diary of a Wimpy Kid', 'Diary of a Wimpy Kid: The Long Haul') == 0


def test_native_box_contract_converts_whole_box_with_explicit_units():
    payload = {'coordinate_system': 'yxyx_1000', 'books': [{
        'title': 'Leading', 'author': None, 'visible_text': 'LEADING', 'uncertain': False,
        'box_2d': [100, 200, 150, 800],
    }]}
    readings, rejected = parse_readings(payload, (1400, 1400))
    assert rejected == 0
    assert readings.books[0].box.model_dump() == pytest.approx({'top': .1, 'left': .2, 'width': .6, 'height': .05})
    assert payload['books'][0]['box_2d'] == [100,200,150,800]
    schema = provider_schema()
    assert 'coordinate_system' in schema['required']
    assert 'box_2d' in schema['$defs']['Reading']['required']


@pytest.mark.parametrize('box', [[100,200,50,800], [.1,.2,.15,.8], [0,0,1001,1000], [0,0,True,1000]])
def test_invalid_native_boxes_preserve_text_without_guessing_units(box):
    payload = {'coordinate_system': 'yxyx_1000', 'books': [{
        'title': 'Leading', 'author': None, 'visible_text': 'LEADING', 'uncertain': False, 'box_2d': box,
    }]}
    parsed, _ = parse_readings(payload, (1400,1400))
    assert parsed.books[0].title == 'Leading'
    assert parsed.books[0].box is None


def test_author_affix_and_generic_subtitle_are_cleaned_without_inventing_title():
    for title,author,text,expected in [
        ('DAN BROWN The Lost Symbol','Dan Brown','DAN BROWN THE LOST SYMBOL','The Lost Symbol'),
        ('Speaking for Myself: the autobiography','Cherie Blair','CHERIE BLAIR SPEAKING FOR MYSELF THE AUTOBIOGRAPHY','Speaking for Myself'),
        ('Horrible Science: Nasty Nature','Nick Arnold','NASTY NATURE NICK ARNOLD','Nasty Nature'),
    ]:
        book = Reading.model_validate(dict(title=title,author=author,visible_text=text,uncertain=False,box=None))
        assert book.title == expected
        assert not book.uncertain


def test_native_whole_number_floats_have_the_same_unambiguous_scale():
    parsed, _ = parse_readings({'coordinate_system':'yxyx_1000','books':[{
        'title':'Leading','author':None,'visible_text':'LEADING','uncertain':False,
        'box_2d':[100.0,200.0,150.0,800.0],
    }]}, (1400,1400))
    assert parsed.books[0].box.left == .2
