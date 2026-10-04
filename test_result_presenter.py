"""Regression tests for the API-to-card contract; no model calls or email sends."""
import unittest
from unittest.mock import patch
from result_presenter import EventFacts, Fact, AccessibilityFact, ActionFacts, EmailDraft, ExtractedResult, serialize

REPORT = '''## Event Details
| Field | Details |
|---|---|
| **Event Name** | City Access Forum |
| **Date** | September 30, 2026 |
| **Time** | 2:00 PM - 3:00 PM Eastern Time |
| **Location** | Online |
| **Organizer/Sponsor** | Community Center |
| **Format** | Live webinar |

| Need | Status | Evidence |
| ASL interpretation | NOT CONFIRMED | ASL is not mentioned. |
| Accessible parking | NOT APPLICABLE | The event is online. |

Email team@example.org for accommodation requests.
To: team@example.org
Subject: Accommodation request
Dear organizer,

Please provide ASL interpretation.

Thank you,
Attendee

Would you like me to send this?'''

def extraction():
    return ExtractedResult(message='Review your event and request draft.', event=EventFacts(**{
        name: Fact(value=value, source_quote=value) for name, value in {
            'name':'City Access Forum','date':'September 30, 2026','time':'2:00 PM - 3:00 PM Eastern Time',
            'location':'Online','organizer':'Community Center','format':'Live webinar'}.items()}),
        accessibility_results=[AccessibilityFact(name='ASL interpretation',status='NOT CONFIRMED',evidence='ASL is not mentioned.',source_quote='| ASL interpretation | NOT CONFIRMED | ASL is not mentioned. |')],
        recommended_action=ActionFacts(official_contact=Fact(value='team@example.org',source_quote='Email team@example.org for accommodation requests.')),
        draft=EmailDraft(to='team@example.org',subject='Accommodation request',body='Dear organizer,\n\nPlease provide ASL interpretation.\n\nThank you,\nAttendee'))

class MappingTests(unittest.TestCase):
    def test_table_has_all_six_real_fields(self):
        result=serialize(extraction(),REPORT,['ASL interpretation'],'https://event.example/one')
        self.assertEqual(result['event']['name'],'City Access Forum')
        self.assertEqual(result['event']['time'],'2:00 PM - 3:00 PM Eastern Time')
        self.assertEqual(result['event']['organizer'],'Community Center')
        self.assertEqual(result['event']['format'],'Live webinar')
        self.assertEqual(result['event']['date'],'September 30, 2026')
        self.assertEqual(result['event']['location'],'Online')
        self.assertNotIn('Would you',result['draft']['body'])

    def test_unsupported_values_and_false_confirmation_rejected(self):
        data=extraction()
        data.event.name=Fact(value='Invented event',source_quote='City Access Forum')
        data.accessibility_results[0].status='CONFIRMED'
        data.draft.body='An invented message'
        result=serialize(data,REPORT,['ASL interpretation','Custom need'],'https://event.example/one')
        self.assertIsNone(result['event']['name'])
        self.assertEqual([n['status'] for n in result['accessibility_results']],['UNKNOWN','UNKNOWN'])
        self.assertIsNone(result['draft'])

    def test_evidence_sentence_uses_the_status_from_its_markdown_row(self):
        data=extraction()
        data.accessibility_results[0].source_quote='ASL is not mentioned.'
        result=serialize(data,REPORT,['ASL interpretation'],'https://event.example/one')
        self.assertEqual(result['accessibility_results'][0]['status'],'NOT CONFIRMED')

    def test_followup_retains_event_but_never_reuses_draft(self):
        old=serialize(extraction(),REPORT,['ASL interpretation'],'https://event.example/one')
        new=serialize(ExtractedResult(message='What would you like to change?'),'What would you like to change?',['ASL interpretation'],'https://event.example/one',old)
        self.assertEqual(new['event'],old['event'])
        self.assertIsNone(new['draft'])

    def test_new_event_does_not_inherit_old_event(self):
        result=serialize(ExtractedResult(message='No details verified.'),'No details verified.',['Custom need'],'https://event.example/two')
        self.assertIsNone(result['event']['name'])
        self.assertEqual(result['event']['url'],'https://event.example/two')

    def test_api_returns_schema_and_formatting_retry_never_calls_agent(self):
        import api
        from fastapi.testclient import TestClient
        class InlineWorker:
            def submit(self, fn, *args): fn(*args)
        class FakeAgent:
            model=None
            count=0
            def __call__(self,message): self.count+=1; return REPORT
        agent=FakeAgent()
        result=serialize(extraction(),REPORT,['ASL interpretation'],'https://event.example/one')
        with patch.object(api,'configure_agent'),patch.object(api,'worker',InlineWorker()),patch.object(api.runpy,'run_path',return_value={'agent':agent}),patch.object(api,'format_result',return_value=result),patch.object(api,'current_user_id',return_value=1),patch.object(api.auth,'user_from_header',return_value=1),patch.object(api,'saved_needs',return_value=['ASL interpretation']),patch.object(api.db,'list_requests',return_value=[]):
            api.jobs.clear();api.sessions.clear();api.session_context.clear()
            client=TestClient(api.app)
            submitted=client.post('/api/events',json={'url':'https://event.example/one'})
            self.assertEqual(submitted.status_code,202)
            job=submitted.json()
            payload=client.get('/api/jobs/'+job['id']).json()
            self.assertEqual(payload['result']['event']['name'],'City Access Forum')
            self.assertEqual(payload['response'],REPORT)
            client.post('/api/jobs/'+job['id']+'/presentation')
            self.assertEqual(agent.count,1)
            with patch.object(api,'format_result',side_effect=ValueError('invalid formatting')), self.assertLogs(level='ERROR'):
                client.post('/api/jobs/'+job['id']+'/presentation')
            failed=client.get('/api/jobs/'+job['id']).json()
            self.assertEqual(failed['status'],'completed')
            self.assertEqual(failed['result']['presentation_status'],'unavailable')
            self.assertEqual(agent.count,1)

if __name__=='__main__': unittest.main()
