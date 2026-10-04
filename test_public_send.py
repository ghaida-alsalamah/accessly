import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import deployment_runtime as runtime
from result_presenter import plain_email

class SendApproval(unittest.TestCase):
    def test_cosmetic_changes_send_exact_approved_text_once(self):
        registry = {}
        browser = SimpleNamespace(_setup_session_from_browser=Mock(), _context_options={}, browser=Mock())
        namespace = {}
        exec('def load_user_profile(): return {}', namespace)
        original = Mock(return_value={"status":"sent"})
        namespace.update(agent=SimpleNamespace(tool_registry=SimpleNamespace(replace=lambda t: registry.update({t.tool_name:t}))), browser=browser, send_accommodation_email=original, create_request_record=Mock())
        context={"reference":"test"}
        with patch.object(runtime, 'PUBLIC', True), patch.object(runtime, 'current_user_id', return_value=1):
            runtime.configure_agent(namespace,context)
            draft={"to":"test@example.invalid", "subject":"Request [Accessly test]", "body":"Dear team,\n\nPlease provide ASL interpretation."}
            context['approval']=dict(draft)
            result=registry['send_accommodation_email'](draft['to'],draft['subject'],'Dear team,\nPlease provide **ASL interpretation**.')
            self.assertEqual(result['status'],'sent')
            original.assert_called_once_with(draft['to'],draft['subject'],draft['body'])
            self.assertEqual(registry['send_accommodation_email'](**dict(recipient=draft['to'],subject=draft['subject'],body=draft['body']))['status'],'failed')
            context['approval']=dict(draft)
            self.assertEqual(registry['send_accommodation_email'](draft['to'],draft['subject'],'Please provide parking.')['status'],'failed')
            original.assert_called_once()
    def test_tracking_preserves_non_applicable_needs(self):
        registry={}
        record={'request_id':1,'accommodations':{'Parking':'PENDING','ASL':'PENDING'}}
        updated={'request_id':1,'accommodations':{'Parking':'NOT APPLICABLE','ASL':'PENDING'}}
        namespace={}
        exec('def load_user_profile(): return {}',namespace)
        namespace.update(agent=SimpleNamespace(tool_registry=SimpleNamespace(replace=lambda t:registry.update({t.tool_name:t}))), browser=SimpleNamespace(_setup_session_from_browser=Mock(),_context_options={},browser=Mock()),send_accommodation_email=Mock(),create_request_record=Mock(return_value={'status':'created','request':record}))
        context={'reference':'test','result':{'accessibility_results':[{'name':'Parking','status':'NOT APPLICABLE'}]}}
        with patch.object(runtime,'PUBLIC',True),patch.object(runtime,'current_user_id',return_value=7),patch.object(runtime.db,'update_request',return_value=updated) as save:
            runtime.configure_agent(namespace,context)
            context['pending_record']={'subject':'subject','recipient':'test@example.invalid'}
            result=registry['create_request_record']('event','https://example.org','test@example.invalid','subject')
            self.assertEqual(result['request']['accommodations'],{'Parking':'NOT APPLICABLE','ASL':'PENDING'})
            save.assert_called_once_with(7,1,{'Parking':'NOT APPLICABLE'})

    def test_plain_email_preserves_paragraphs(self):
        self.assertEqual(plain_email('Dear team,\n\nPlease provide **ASL interpretation**.'),'Dear team,\n\nPlease provide ASL interpretation.')

if __name__=='__main__': unittest.main()
