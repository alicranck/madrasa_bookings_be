from typing import List

from app.aux_functions import _convert_query_results_to_dict
from app.mailing_utils import _create_message, _send_message, _create_event
from application import application, engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy import *
from flask import flash, request, jsonify, render_template, session as flask_session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.orm import Session
from flask_cors import CORS, cross_origin
import uuid
import re
import sys
from datetime import datetime, timedelta

CORS(application, support_credentials=True)
Base = automap_base()
Base.prepare(engine, reflect=True)
Teachers = Base.classes.teachers
Students = Base.classes.students
Events = Base.classes.events
Bundles = Base.classes.bundles

# teacher_events = Base.classes.teacher_event_pointers
# student_events = Base.classes.student_event_pointers

MAIL_ADDRESS = "alicranck@gmail.com"
MAIL_SERVICE = ""
SERVER_IP = ""

session = Session(engine)
metadata = MetaData(engine)

event_status_map = {"available": 0, "pending": 1, "booked": 2, "cancelled": 3, "done": 4}


@application.route('/', methods=["GET", "POST"])
def entry():
    return render_template('index.html')


@application.route('/add_teacher', methods=["POST"])
def add_teacher():
    request_data = request.get_json()
    id_exists = bool(session.query(Teachers).filter_by(id=request_data["teacher_id"]).first())
    if id_exists:
        return {"message": "Teacher ID exists"}

    teachers_t = Table('teachers', metadata, autoload=True)

    engine.execute(teachers_t.insert(), id=request_data['teacher_id'], first_name=request_data['first_name'],
                   last_name=request_data['last_name'], age=request_data['age'], email=request_data['email'],
                   phone_number=request_data['phone_number'], bio=request_data['bio'],
                   interests=request_data['interests'])

    return {"message": "Teacher added successfully"}


@application.route('/add_student', methods=["POST"])
def add_student():
    request_data = request.get_json()
    id_exists = bool(session.query(Students).filter_by(id=request_data["student_id"]).first())
    if id_exists:
        return {"message": "Student ID exists"}

    students_t = Table('students', metadata, autoload=True)

    engine.execute(students_t.insert(), id=request_data['student_id'], first_name=request_data['first_name'],
                   last_name=request_data['last_name'], age=request_data['age'], email=request_data['email'],
                   phone_no=request_data['phone_number'], gender=request_data['gender'],
                   interests=request_data['interests'])

    return {"message": "Student added successfully"}


@application.route('/add_recurring_timeslot', methods=["GET", "POST"])
def add_recurring_timeslot():

    if request.method == "POST":

        request_data = request.get_json()

        # Get event info
        student_ids = "[]"
        teacher_ids = request_data['teacher_ids']

        event_info = ""

        start_datetime = datetime.fromisoformat(request_data['start_datetime'])
        end_datetime = datetime.fromisoformat(request_data['end_datetime'])
        duration_minutes = request_data['duration_minutes']
        interval_days = request_data['interval_days']

        current_datetime = start_datetime
        delta = timedelta(days=interval_days)

        events_t = Table('events', metadata, autoload=True)

        while current_datetime < end_datetime:
            event_id = _generate_event_id(teacher_ids, current_datetime.isoformat())
            _add_single_event(events_t, event_id, event_info, student_ids, teacher_ids, current_datetime,
                              duration_minutes)
            current_datetime += delta

        return {"message": "event added successfully"}


@application.route('/book_event_bundle', methods=["GET", "POST"])
def book_event_bundle():
    if request.method == "POST":
        # Get event info
        request_data = request.get_json()
        student_ids = request_data['student_ids']
        teacher_ids = request_data['teacher_ids']

        start_datetime = datetime.fromisoformat(request_data['start_datetime'])
        recurrences = request_data['recurrences']
        interval_days = request_data['interval_days']

        current_datetime = start_datetime
        delta = timedelta(days=interval_days)

        events_t = Table('events', metadata, autoload=True)
        event_ids = []
        for _ in range(recurrences):
            event_id = _generate_event_id(teacher_ids, current_datetime.isoformat())
            event_ids.append(event_id)
            if not _is_event_available(event_id):
                return {"message": "unable to book"}
            current_datetime += delta

        bundle_id = event_ids[0]
        bundles_t = Table('bundles', metadata, autoload=True)

        engine.execute(bundles_t.insert(), id=bundle_id, events=event_ids)

        for event_id in event_ids:
            _book_single_event(events_t, event_id, student_ids, bundle_id)

        # TODO send confirmation request to teachers

        return {"message": "booked successfully"}


@application.route('/confirm_event_bundle', methods=["GET", "POST"])
def confirm_event_bundle():
    if request.method == "POST":
        # Get event info
        request_data = request.args
        bundle_id = request_data['bundle_id']

        bundle_query_res = session.query(Bundles).filter(Bundles.id == bundle_id)
        bundle_data = _convert_query_results_to_dict(bundle_query_res)[0]
        events_t = Table('events', metadata, autoload=True)

        # Test events availability (should be pending)
        for event_id in bundle_data['events']:
            if not _is_event_available(event_id, required_status=event_status_map["pending"]):
                return {"message": "unable to confirm"}

        # Collect events
        events_query_res = session.query(Events).filter(Events.event_id.in_(bundle_data['events'])).all()
        events_data = _convert_query_results_to_dict(events_query_res)

        # Confirm events in database and collect calendar data
        event_periods, teacher_ids, student_ids = [], [], []
        for event_data in events_data:
            _confirm_single_event(events_t, event_data['event_id'])

            start_time = datetime.fromisoformat(event_data['timestamp'])
            duration = timedelta(minutes=event_data['duration'])
            period = (start_time, start_time + duration)
            event_periods.append(period)

            teacher_ids.extend(event_data['teachers'])
            student_ids.extend((event_data['students']))
            
        atendees_emails = []
        for t_id in teacher_ids:
            teacher_query_res = session.query(Teachers).filter(Teachers.id == t_id)
            teacher_data = _convert_query_results_to_dict(teacher_query_res)
            atendees_emails.append(teacher_data['email'])
            
        for t_id in student_ids:
            student_query_res = session.query(Students).filter(Students.id == t_id)
            student_data = _convert_query_results_to_dict(student_query_res)
            atendees_emails.append(student_data['email'])

        # Add events to calendar
        _create_event(event_periods, atendees_emails)

        return {"message": "booked successfully"}


@application.route('/get_available_events', methods=["GET"])
def get_available_events():

    # Get request data
    request_data = request.args
    current_datetime = datetime.fromisoformat(request_data['start_datetime'])
    available_events_query = session.query(Events).filter(Events.timestamp > current_datetime).filter(
        Events.event_status == event_status_map["available"]).all()

    available_events = _convert_query_results_to_dict(available_events_query)

    return jsonify(available_events)


@application.route('/get_all_events', methods=["GET"])
def get_all_events():

    # Get request data
    request_data = request.args
    current_datetime = datetime.fromisoformat(request_data['start_datetime'])
    available_events_query = session.query(Events).filter(Events.timestamp > current_datetime).all()

    available_events = _convert_query_results_to_dict(available_events_query)

    return jsonify(available_events)


@application.route('/delete_event', methods=["POST"])
def delete_event():
    request_data = request.get_json()

    id_exists = bool(session.query(Events).filter_by(event_id=request_data["event_id"]).first())
    if not id_exists:
        return {"message": "event not in db"}

    event_query_res = session.query(Events).filter(Events.event_id == request_data["event_id"])
    event_data = _convert_query_results_to_dict(event_query_res)[0]
    print(event_data)

    bundle_t = Table('bundles', metadata, autoload=True)

    if event_data['bundle_id']:
        bundle_query_res = session.query(Bundles).filter(Bundles.id == event_data["bundle_id"])
        bundle_data = _convert_query_results_to_dict(bundle_query_res)[0]
        print(bundle_data)
        bundle_events = bundle_data['events']
        updated_events = [e for e in bundle_events if e != event_data['bundle_id']]

        engine.execute(bundle_t.update().where(bundle_t.c.id == event_data['bundle_id']).values(events=updated_events))

    events_t = Table('events', metadata, autoload=True)
    engine.execute(events_t.delete().where(events_t.c.event_id == request_data["event_id"]))
    return {"message": "event deleted"}


def _add_single_event(events_table, event_id, event_info, student_ids, teacher_ids, datetime, duration_minutes):
    engine.execute(events_table.insert(), event_id=event_id, event_name="lesson",
                   event_info=event_info, timestamp=datetime, event_status=event_status_map["available"],
                   modified_flag=0, students=student_ids, teachers=teacher_ids, duration=duration_minutes)
    return 0


def _book_single_event(events_table, event_id, student_ids, bundle_id):

    engine.execute(events_table.update().where(events_table.c.event_id == event_id).values(
        students=student_ids).values(event_status=event_status_map["pending"]).values(bundle_id=bundle_id))

    return 0


def _confirm_single_event(events_table, event_id):

    engine.execute(events_table.update().where(events_table.c.event_id == event_id).values(
        event_status=event_status_map["booked"]))

    return 0


def _generate_event_id(teacher_ids: List[str], timestamp: str):
    uid = '_'.join(teacher_ids) + "|" + timestamp
    return uid


def _is_event_available(event_id, required_status=event_status_map['available']):

    res = session.query(Events).filter(Events.event_id == event_id)

    parsed_res = _convert_query_results_to_dict(res)
    print(parsed_res)
    if len(parsed_res) != 1 or parsed_res[0]['event_status'] != required_status:
        return 0
    return -1


def _send_confirmation_request(start_event_id, n_recurrences):

    if not _is_event_available(start_event_id):
        return -1

    event_query_res = session.query(Events).filter(Events.event_id == start_event_id)
    event_data = _convert_query_results_to_dict(event_query_res)[0]

    students_query_res = session.query(Students).filter(Students.id.in_(event_data["students"])).all()
    students_data = _convert_query_results_to_dict(students_query_res)

    for teacher_id in event_data['teachers']:

        teacher_query_res = session.query(Teachers).filter(Teachers.id == teacher_id)
        teacher_data = _convert_query_results_to_dict(teacher_query_res)[0]

        confirmation_url = f'{SERVER_IP}/confirm_event_bundle?teacher_ids=[{teacher_data["id"]}]&start_datetime=' \
                           f'{event_data["timestamp"]}&recurrences={n_recurrences}'

        mail_txt = f"Dear {teacher_data['first_name']},\nThe following students have requested to schedule " \
                   f"{n_recurrences} weekly 30 minutes sessions with you, starting in {event_data['timestamp']}:\n" \
                   f"{', '.join([d['first_name'] + ' ' + d['last_name'] for d in students_data])}.\n" \
                   f"Please follow the link to confirm: {confirmation_url}"

        e_message = _create_message(MAIL_ADDRESS, teacher_data["email"], "Lesson bundle confirmation", mail_txt)
        _send_message(MAIL_SERVICE, "me", e_message)

    return


