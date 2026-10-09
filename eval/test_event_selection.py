"""Validate the fresh synthetic source-selection freeze without model inference."""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / 'eval/dev'
sys.path.insert(0, str(ROOT))
os.environ['ORT_DISABLE_TELEMETRY'] = '1'


def read_rows(name):
    return [json.loads(line) for line in (DEV / name).read_text().splitlines()]


def test_fresh_selection_freeze():
    from robot.text_embed import TextEmbedder

    manifest = json.loads((DEV / 'event-selection-2.freeze.json').read_text())
    assert manifest['slot_map'] == {'observation': 'observed', 'utterance': 'dialogue'}
    assert (hashlib.sha256((ROOT / manifest['protocol_file']).read_bytes()).hexdigest()
            == manifest['protocol_sha256'])
    tokenizer = ROOT / manifest['tokenizer']['path']
    assert hashlib.sha256(tokenizer.read_bytes()).hexdigest() == manifest['tokenizer']['sha256']
    tok = Tokenizer.from_file(str(tokenizer))
    tok.no_truncation()
    tok.no_padding()
    embedder = TextEmbedder.__new__(TextEmbedder)
    embedder.tok = tok
    calibration = read_rows('event-calibration-2.jsonl')
    comparison = read_rows('event-retrieval-2.jsonl')
    assert Counter(r['kind'] for r in calibration) == {'observation': 16, 'utterance': 16}
    assert Counter(r['category'] for r in comparison) == {
        'older-observation': 8, 'topic-reference': 8, 'correction': 8, 'absent-evidence': 8,
    }
    assert len({r['source_group'] for r in calibration + comparison}) == 64
    assert len({r['world_name'] for r in calibration + comparison}) == 64
    texts = set()
    long_kinds = Counter()
    for filename, metadata in manifest['files'].items():
        path = ROOT / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata['sha256']
        assert len(path.read_text().splitlines()) == metadata['questions']
    for row in calibration + comparison:
        assert row['schema_version'] == 2
        assert len(row['sources']) >= 5
        sources = {s['id']: s for s in row['sources']}
        assert len(sources) == len(row['sources'])
        expected_pairs = {(s['id'], k) for s in row['sources']
                          for k in ('observation', 'utterance')}
        labels = {(x['source_id'], x['kind']): x for x in row['source_kind_labels']}
        assert len(labels) == len(row['source_kind_labels'])
        assert set(labels) == expected_pairs
        sufficient = {key for key, value in labels.items() if value['sufficient']}
        assert all(not x['sufficient'] or x['relevant'] for x in labels.values())
        assert sufficient == {(x['source_id'], x['kind']) for x in row['decisive_spans']}
        assert set(row['sufficient_source_ids']) == {key[0] for key in sufficient}
        assert row['expected_source_ids'] == row['sufficient_source_ids']
        for source in sources.values():
            assert source['source_group'] == row['source_group']
            assert (source['ts'] < source['utterance_start']
                    < source['utterance_end'] < row['query_at'])
            for field in ('said', 'caption'):
                assert source[field] and source[field] not in texts
                texts.add(source[field])
                indexed = embedder.units(source[field])
                assert ''.join(unit['text'] for unit in indexed) == source[field]
                assert all(unit['tokens'] <= 128 for unit in indexed)
        if 'category' in row:
            distractors = [s for s in sources.values() if '-newer-' in s['id']]
            assert len(distractors) >= 4
            assert all(s['ts'] > 1000 for s in distractors)
            assert all(not labels[(s['id'], k)]['relevant'] for s in distractors
                       for k in ('observation', 'utterance'))
        for span in row['decisive_spans']:
            text = sources[span['source_id']][
                'caption' if span['kind'] == 'observation' else 'said']
            assert 0 <= span['start'] < span['end'] <= len(text)
            assert text[span['start']:span['end']] == span['text']
            if span['source_id'] in row.get('long_source_ids', []):
                assert len(tok.encode(text[:span['start']], add_special_tokens=False).ids) > 128
                assert any(unit['start'] <= span['start'] and span['end'] <= unit['end']
                           for unit in embedder.units(text))
                long_kinds[span['kind']] += 1
    assert long_kinds == {'observation': 2, 'utterance': 2}
    assert sum((DEV / name).stat().st_size for name in (
        'event-calibration-2.jsonl', 'event-retrieval-2.jsonl', 'event-selection-2.freeze.json',
    )) + Path(__file__).stat().st_size < 1_000_000


if __name__ == '__main__':
    test_fresh_selection_freeze()
    print('Fresh selection freeze: 64 cases, all hashes, labels, spans, units, '
          'and split checks passed.')
