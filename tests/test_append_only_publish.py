import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import dedication_feedback, publish_daily, sync_from_google_sheet, utils


def make_dedication(date_str, status):
    return {
        'id': f'ded-{date_str}',
        'date': date_str,
        'day_name': '',
        'status': status,
        'song_title': f'Song {date_str}',
        'artist': 'Artist',
        'dedication_title': f'Title {date_str}',
        'dedication_text': f'Text {date_str}',
        'audio': {'url': 'https://example.com/audio', 'type': 'other'},
        'vote': {'url': 'https://example.com/vote'},
        'image': {'path': f'/images/dedications/{date_str}.webp', 'alt': 'Alt', 'mode': 'none', 'source': ''},
        'short_phrase': '',
        'tags': [],
        'seo': {'title': 'SEO', 'description': 'Description'},
        'created_at': '2026-05-10T00:00:00+02:00',
        'updated_at': '2026-05-10T00:00:00+02:00',
    }


def make_row(date_str, status):
    ded = make_dedication(date_str, status)
    return {
        'id': ded['id'],
        'date': date_str,
        'status': status,
        'song_title': ded['song_title'],
        'artist': ded['artist'],
        'dedication_title': ded['dedication_title'],
        'dedication_text': ded['dedication_text'],
        'audio_url': ded['audio']['url'],
        'audio_type': ded['audio']['type'],
        'vote_url': ded['vote']['url'],
        'image_mode': ded['image']['mode'],
        'image_source': '',
        'short_phrase': '',
        'tags': '',
        'seo_title': '',
        'seo_description': '',
        'image_alt': '',
    }


class AppendOnlyPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / 'data' / 'dedications'
        self.data_dir.mkdir(parents=True)

        patches = [
            patch.object(utils, 'ROOT_DIR', self.root),
            patch.object(utils, 'DATA_DIR', self.data_dir),
        ]
        self.patchers = patches
        for patcher in patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def write_dedication(self, date_str, status):
        path = self.data_dir / f'{date_str}.json'
        path.write_text(json.dumps(make_dedication(date_str, status)), encoding='utf-8')

    def read_dedication(self, date_str):
        return json.loads((self.data_dir / f'{date_str}.json').read_text(encoding='utf-8'))

    def test_wednesday_publish_preserves_monday_and_tuesday_archive(self):
        self.write_dedication('2026-05-11', 'published')
        self.write_dedication('2026-05-12', 'published')
        self.write_dedication('2026-05-13', 'scheduled')

        tuesday_before = self.read_dedication('2026-05-12')
        rows = [
            make_row('2026-05-11', 'published'),
            make_row('2026-05-12', 'published'),
            make_row('2026-05-13', 'scheduled'),
        ]

        sync_ok = sync_from_google_sheet.sync_rows(
            rows,
            default_vote_url='https://example.com/vote',
            target_date='2026-05-13',
        )
        self.assertTrue(sync_ok)

        fake_generate = types.ModuleType('scripts.generate_image')
        fake_generate.ensure_fonts = lambda: {}
        fake_generate.generate_for_dedication = lambda ded, fonts, dry_run=False: True

        with patch.dict(sys.modules, {'scripts.generate_image': fake_generate}):
            publish_ok = publish_daily.publish('2026-05-13')

        self.assertTrue(publish_ok)
        self.assertEqual(self.read_dedication('2026-05-11')['status'], 'published')
        self.assertEqual(self.read_dedication('2026-05-12'), tuesday_before)
        self.assertEqual(self.read_dedication('2026-05-13')['status'], 'published')
        self.assertTrue((self.data_dir / '2026-05-11.json').exists())
        self.assertTrue((self.data_dir / '2026-05-12.json').exists())
        self.assertTrue((self.data_dir / '2026-05-13.json').exists())

    def test_sync_does_not_overwrite_published_without_force(self):
        self.write_dedication('2026-05-12', 'published')
        before = self.read_dedication('2026-05-12')

        row = make_row('2026-05-12', 'scheduled')
        row['song_title'] = 'Changed in sheet'

        sync_ok = sync_from_google_sheet.sync_rows(
            [row],
            default_vote_url='https://example.com/vote',
        )

        self.assertTrue(sync_ok)
        self.assertEqual(self.read_dedication('2026-05-12'), before)

    def test_publish_all_dedications_for_same_date(self):
        first = make_dedication('2026-05-14', 'scheduled')
        first['id'] = '2026-05-14-first-song'
        second = make_dedication('2026-05-14', 'scheduled')
        second['id'] = '2026-05-14-second-song'
        (self.data_dir / f"{first['id']}.json").write_text(json.dumps(first), encoding='utf-8')
        (self.data_dir / f"{second['id']}.json").write_text(json.dumps(second), encoding='utf-8')

        fake_generate = types.ModuleType('scripts.generate_image')
        fake_generate.ensure_fonts = lambda: {}
        fake_generate.generate_for_dedication = lambda ded, fonts, dry_run=False: True

        with patch.dict(sys.modules, {'scripts.generate_image': fake_generate}):
            publish_ok = publish_daily.publish('2026-05-14')

        self.assertTrue(publish_ok)
        first_after = json.loads((self.data_dir / f"{first['id']}.json").read_text(encoding='utf-8'))
        second_after = json.loads((self.data_dir / f"{second['id']}.json").read_text(encoding='utf-8'))
        self.assertEqual(first_after['status'], 'published')
        self.assertEqual(second_after['status'], 'published')
        self.assertEqual(first_after['image']['path'], '/images/dedications/2026-05-14-first-song.webp')
        self.assertEqual(second_after['image']['path'], '/images/dedications/2026-05-14-second-song.webp')

    def test_publish_can_target_one_dedication_for_same_date(self):
        first = make_dedication('2026-05-15', 'scheduled')
        first['id'] = '2026-05-15-first-song'
        second = make_dedication('2026-05-15', 'scheduled')
        second['id'] = '2026-05-15-second-song'
        (self.data_dir / f"{first['id']}.json").write_text(json.dumps(first), encoding='utf-8')
        (self.data_dir / f"{second['id']}.json").write_text(json.dumps(second), encoding='utf-8')

        fake_generate = types.ModuleType('scripts.generate_image')
        fake_generate.ensure_fonts = lambda: {}
        fake_generate.generate_for_dedication = lambda ded, fonts, dry_run=False: True

        with patch.dict(sys.modules, {'scripts.generate_image': fake_generate}):
            publish_ok = publish_daily.publish('2026-05-15', target_id=first['id'])

        self.assertTrue(publish_ok)
        first_after = json.loads((self.data_dir / f"{first['id']}.json").read_text(encoding='utf-8'))
        second_after = json.loads((self.data_dir / f"{second['id']}.json").read_text(encoding='utf-8'))
        self.assertEqual(first_after['status'], 'published')
        self.assertEqual(second_after['status'], 'scheduled')

    def test_update_vote_persists_feedback_fields(self):
        self.write_dedication('2026-05-16', 'published')
        path = self.data_dir / '2026-05-16.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['id'] = 'ded-2026-05-16'
        path.write_text(json.dumps(data), encoding='utf-8')

        updated = dedication_feedback.update_vote(
            'ded-2026-05-16',
            8,
            'Pensiero salvato',
            user_id='user-a',
            user_name='Mario',
        )

        self.assertEqual(updated['voteAverage'], 8)
        self.assertEqual(updated['thoughtsText'], '[Mario] Pensiero salvato')
        self.assertEqual(updated['votes'][0]['userId'], 'user-a')
        self.assertEqual(updated['thoughts'][0]['userName'], 'Mario')
        saved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(saved['voteAverage'], 8)
        self.assertEqual(saved['thoughtsText'], '[Mario] Pensiero salvato')
        self.assertEqual(saved['reactions'], {'down': 0, 'like': 0, 'heart': 0, 'sun': 0})

    def test_update_reaction_can_switch_and_remove_browser_choice(self):
        self.write_dedication('2026-05-18', 'published')
        path = self.data_dir / '2026-05-18.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['id'] = 'ded-2026-05-18'
        path.write_text(json.dumps(data), encoding='utf-8')

        first = dedication_feedback.update_reaction('ded-2026-05-18', 'heart', user_id='user-a', user_name='Mario')
        self.assertEqual(first['reactions'], {'down': 0, 'like': 0, 'heart': 1, 'sun': 0})

        removed = dedication_feedback.update_reaction('ded-2026-05-18', None, 'heart', user_id='user-a', user_name='Mario')
        self.assertEqual(removed['reactions'], {'down': 0, 'like': 0, 'heart': 0, 'sun': 0})

        sun = dedication_feedback.update_reaction('ded-2026-05-18', 'sun', user_id='user-a', user_name='Mario')
        self.assertEqual(sun['reactions'], {'down': 0, 'like': 0, 'heart': 0, 'sun': 1})

        switched = dedication_feedback.update_reaction('ded-2026-05-18', 'heart', 'sun', user_id='user-a', user_name='Mario')
        self.assertEqual(switched['reactions'], {'down': 0, 'like': 0, 'heart': 1, 'sun': 0})

    def test_feedback_is_nominal_and_updates_only_same_user(self):
        self.write_dedication('2026-05-19', 'published')
        path = self.data_dir / '2026-05-19.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['id'] = 'ded-2026-05-19'
        path.write_text(json.dumps(data), encoding='utf-8')

        dedication_feedback.update_vote('ded-2026-05-19', 8, 'Bella', user_id='mario-id', user_name='Mario')
        dedication_feedback.update_vote('ded-2026-05-19', 10, 'Perfetta', user_id='anna-id', user_name='Anna')
        updated = dedication_feedback.update_vote('ded-2026-05-19', 9, 'Ancora meglio', user_id='mario-id', user_name='Mario')

        self.assertEqual(len(updated['votes']), 2)
        self.assertEqual(updated['voteAverage'], 9.5)
        self.assertEqual({vote['userName']: vote['value'] for vote in updated['votes']}, {'Mario': 9, 'Anna': 10})
        self.assertIn('[Mario] Ancora meglio', updated['thoughtsText'])
        self.assertIn('[Anna] Perfetta', updated['thoughtsText'])

        dedication_feedback.update_reaction('ded-2026-05-19', 'heart', user_id='mario-id', user_name='Mario')
        dedication_feedback.update_reaction('ded-2026-05-19', 'sun', user_id='anna-id', user_name='Anna')
        reactions = dedication_feedback.update_reaction('ded-2026-05-19', 'like', 'heart', user_id='mario-id', user_name='Mario')

        self.assertEqual(len(reactions['reactionEntries']), 2)
        self.assertEqual(reactions['reactions'], {'down': 0, 'like': 1, 'heart': 0, 'sun': 1})

    def test_feedback_uses_stable_user_key_across_browser_ids(self):
        self.write_dedication('2026-05-20', 'published')
        path = self.data_dir / '2026-05-20.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['id'] = 'ded-2026-05-20'
        path.write_text(json.dumps(data), encoding='utf-8')

        dedication_feedback.update_vote(
            'ded-2026-05-20',
            8,
            'Primo browser',
            user_id='chrome-random-id',
            user_name=' Maxwell  Ferrando ',
        )
        updated = dedication_feedback.update_vote(
            'ded-2026-05-20',
            9,
            'Secondo browser',
            user_id='edge-random-id',
            user_name='MAXWELL FERRANDO',
        )

        self.assertEqual(len(updated['votes']), 1)
        self.assertEqual(updated['votes'][0]['userKey'], 'maxwell-ferrando')
        self.assertEqual(updated['votes'][0]['value'], 9)
        self.assertEqual(updated['thoughts'][0]['text'], 'Secondo browser')

        dedication_feedback.update_reaction(
            'ded-2026-05-20',
            'heart',
            user_id='chrome-random-id',
            user_name='Maxwell Ferrando',
        )
        reactions = dedication_feedback.update_reaction(
            'ded-2026-05-20',
            'sun',
            'heart',
            user_id='mobile-random-id',
            user_name=' maxwell ferrando ',
        )

        self.assertEqual(len(reactions['reactionEntries']), 1)
        self.assertEqual(reactions['reactionEntries'][0]['userKey'], 'maxwell-ferrando')
        self.assertEqual(reactions['reactionEntries'][0]['value'], 'sun')
        self.assertEqual(reactions['reactions'], {'down': 0, 'like': 0, 'heart': 0, 'sun': 1})

    def test_sync_preserves_existing_feedback_when_forced(self):
        self.write_dedication('2026-05-17', 'scheduled')
        path = self.data_dir / '2026-05-17.json'
        before = json.loads(path.read_text(encoding='utf-8'))
        before['voteAverage'] = 9
        before['thoughtsText'] = 'Da non perdere'
        before['reactions'] = {'down': 0, 'like': 2, 'heart': 4, 'sun': 1}
        path.write_text(json.dumps(before), encoding='utf-8')

        row = make_row('2026-05-17', 'scheduled')
        row['song_title'] = 'Changed in sheet'
        sync_ok = sync_from_google_sheet.sync_rows(
            [row],
            default_vote_url='https://example.com/vote',
            force_republish=True,
        )

        self.assertTrue(sync_ok)
        after = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(after['song_title'], 'Changed in sheet')
        self.assertEqual(after['voteAverage'], 9)
        self.assertEqual(after['thoughtsText'], '[Storico] Da non perdere')
        self.assertEqual(after['reactions'], {'down': 0, 'like': 2, 'heart': 4, 'sun': 1})


if __name__ == '__main__':
    unittest.main()
