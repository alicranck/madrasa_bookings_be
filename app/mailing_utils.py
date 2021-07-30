import base64
from email import errors
from email.mime.text import MIMEText

from gcsa.event import Event
from gcsa.reminders import EmailReminder

from app.aux_functions import _convert_query_results_to_dict

from gcsa.google_calendar import GoogleCalendar

calendar = None #GoogleCalendar(credentials_path=
                 #         r'C:\Almog\tech2peace\hackathon_booking_system\madrasa-bookings-master\madrasa-bookings-master\credentials.json')


def _create_event(event_periods, atendee_emails):
    event = Event('Arabic lesson',
                  start=event_periods[0][0],
                  end=event_periods[0][1],
                  recurrence=event_periods,
                  attendees=atendee_emails)
    calendar.add_event(event, EmailReminder(minutes_before_start=30))

    return


def _create_message(sender, to, subject, message_text):
  """Create a message for an email.

  Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

  Returns:
    An object containing a base64url encoded email object.
  """
  message = MIMEText(message_text)
  message['to'] = to
  message['from'] = sender
  message['subject'] = subject
  return {'raw': base64.urlsafe_b64encode(message.as_string())}


def _send_message(service, user_id, message):
  """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
  try:
    message = (service.users().messages().send(userId=user_id, body=message)
               .execute())
    print('Message Id: %s' % message['id'])
    return message
  except errors.HttpError as error:
    print('An error occurred: %s' % error)