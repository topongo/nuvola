import datetime
import json
from getpass import getpass
from http.client import HTTPSConnection
from .scraper import scrape_from_credentials, scrape_from_token, ExpiredSessionTokenException
from .version import VERSION


def check_for_json(obj, with_dates=False):
    if type(obj) in (int, float, dict, list, str, bool) or obj is None:
        return True
    else:
        return with_dates and obj in (datetime.date, datetime.datetime, datetime.time)


class Nuvola:
    def __init__(self, id_student, **kwargs):
        self.id_student = id_student
        t1 = datetime.datetime.now()
        self.conn = self.Connection()
        print("[ OK ] Connection ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
        if "old_data" in kwargs and type(kwargs["old_data"]) is dict:
            self.__init_from_dict(kwargs["old_data"])
            return
        t1 = datetime.datetime.now()
        self.homeworks = self.Homeworks(self)
        print("[ OK ] Homeworks ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
        t1 = datetime.datetime.now()
        self.events = self.Events(self)
        print("[ OK ] Events ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
        t1 = datetime.datetime.now()
        self.time_windows = self.__load_time_windows()
        print("[ OK ] TimeWindows ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
        self.active_time_window = self.__select_best_time_window()

    def __init_from_dict(self, obj):
        class FormatErrorException(Exception):
            pass

        class VersionMismatchException(Exception):
            pass

        if not all([i in ("homeworks", "events", "timeWindows", "version") for i in obj.keys()]):
            raise FormatErrorException(obj)
        if obj["version"] == VERSION or input("Data from import obj is from another version, continue? (y,N) ") == "y":
            t1 = datetime.datetime.now()
            self.homeworks = self.Homeworks(self, old_data=obj["homeworks"])
            print("[ OK ] Homeworks ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
            t1 = datetime.datetime.now()
            self.events = self.Events(self, old_data=obj["events"])
            print("[ OK ] Events ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
            t1 = datetime.datetime.now()
            self.time_windows = self.__load_time_windows(obj["timeWindows"])
            print("[ OK ] TimeWindows ({} seconds)".format((datetime.datetime.now() - t1).total_seconds()))
            self.active_time_window = self.__select_best_time_window()
        else:
            raise VersionMismatchException(f"{VERSION} != {obj['version']}")

    def get(self, area):
        url = "/api-studente/v1/alunno/{}/{}".format(self.id_student, area)
        d = self.conn.get_data(url)
        return d["valori"]

    def get_custom(self, custom_url):
        d = self.conn.get_data(custom_url)
        return d

    def __load_time_windows(self, old_data=None):
        if old_data is not None:
            return [self.TimeWindow(self, i["raw"], old_data=i) for i in old_data]
        return [self.TimeWindow(self, i) for i in self.get("frazioni-temporali")]

    def __load_irregularities(self):
        return [self.Irregularity(i, self) for i in self.get("assenze")]

    def get_time_windows(self):
        for i in self.time_windows:
            yield i

    class Connection:
        class RequestErrorException(Exception):
            pass

        def __init__(self, **kwargs):
            self.c = HTTPSConnection("nuvola.madisoft.it")
            try:
                with open("u.tok", "r") as f:
                    self.u_token = f.read()
                self.s_token = None
            except FileNotFoundError:
                try:
                    with open("s.tok", "r") as f:
                        self.s_token = f.read()
                except FileNotFoundError:
                    self.s_token = None
                self.refresh_tokens()

        def refresh_tokens(self):
            try:
                self.u_token = scrape_from_token(self.s_token)
            except ExpiredSessionTokenException:
                print("Expired session token, please use credentials")
                self.s_token, self.u_token = scrape_from_credentials(input("Username: "), getpass("Password: "))
            with open("s.tok", "w") as f:
                f.write(self.s_token)
            with open("u.tok", "w") as f:
                f.write(self.u_token)

        def get_data(self, url):
            self.c.request("GET", url, headers={"Authorization": "Bearer " + self.u_token})
            j_r = self.c.getresponse()
            j = json.load(j_r)
            if j == "Errore":
                raise self.RequestErrorException(j)
            if "code" in j and j["code"] == 401:
                print("Token expired, getting a new one...")
                self.refresh_tokens()
                return self.get_data(url)
            else:
                return j

    def get_curl_to_file(self, file):
        if type(file) is not Nuvola.File:
            raise TypeError(file)
        return "curl \"https://nuvola.madisoft.it/{}\" -H \"Authorization: {}\"".format(
            file.parent_class.ATTACHMENT_LINK.format(self.id_student, file.uuid), self.conn.u_token)

    class IncompatibleTimeWindowException(Exception):
        pass

    class MissingSuitableTimeWindowException(Exception):
        pass

    def __select_best_time_window(self):
        # Try to get entire year, else try to get current window
        for i in self.get_time_windows():
            if i.name == "INTERO ANNO":
                return i
        for i in self.get_time_windows():
            if i.current:
                return i
        raise self.MissingSuitableTimeWindowException()

    def set_time_window(self, tw):
        if tw in self.get_time_windows():
            self.active_time_window = tw
        else:
            raise self.IncompatibleTimeWindowException(tw)

    class Homeworks:
        def __init__(self, parent, max_empty_days=15*4, **kwargs):
            self.parent = parent
            self.max_empty_days = max_empty_days
            self.refresh_time = datetime.timedelta(hours=6)
            self.data = []
            if "old_data" in kwargs and type(kwargs["old_data"]) is dict:
                self.__init_from_dict(kwargs["old_data"])
                return
            self.mod_time = datetime.datetime.now()
            self.load()

        def __init_from_dict(self, obj):
            for i in obj["data"]:
                self.data.append(Nuvola.Homework(i))
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])

        def load(self):
            date_s = datetime.date(year=2020, month=8, day=30) + datetime.timedelta(days=1)
            date_e = date_s + datetime.timedelta(days=15)
            empty_count = 0
            self.data = []
            while True:
                # for each iteration we ask nuvola homeworks in a period of time of 15 days
                c = self.parent.get("compito/elenco/{}/{}".format(
                    date_s.strftime("%d-%m-%Y"), date_e.strftime("%d-%m-%Y")))
                if len(c) == 0:
                    empty_count += 1
                else:
                    self.data += [Nuvola.Homework(i) for i in c]
                    empty_count = 0
                if empty_count >= self.max_empty_days / 15:
                    break
                date_s = date_e + datetime.timedelta(days=1)
                date_e += datetime.timedelta(days=15)
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.refresh_time:
                self.load()

        def get_by_assignment_date(self, date):
            self.check_and_update()
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if i.date_assigned == date:
                    yield i

        def get_by_expiration_date(self, date):
            self.check_and_update()
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if i.date_expired == date:
                    yield i

        def get_all(self):
            self.check_and_update()
            for i in self.data:
                yield i

        def set_refresh_time(self, time: datetime.timedelta):
            if type(time) is not datetime.timedelta:
                raise TypeError(time)
            self.refresh_time = time

    class Homework:
        ATTACHMENT_LINK = "/api-studente/v1/alunno/{}/compito/allegato/{}"

        def __init__(self, h):
            self.teacher = h["docente"]
            self.subject = h["materia"]
            self.attachments = [Nuvola.File(i, self.__class__) for i in h["allegati"]]
            self.class_ = h["classe"]
            self.class_id = h["classeId"]
            self.date_assigned = datetime.date.fromisoformat(h["dataAssegnazione"][:10])
            self.date_expired = datetime.date.fromisoformat(h["dataConsegna"][:10])
            self.description = h["descrizioneCompito"][0]
            self.raw = h

    class Events:
        def __init__(self, parent, **kwargs):
            self.parent = parent
            self.refresh_time = datetime.timedelta(hours=6)
            self.data = []
            if "old_data" in kwargs and type(kwargs["old_data"]) is dict:
                self.__init_from_dict(kwargs["old_data"])
                return
            self.mod_time = datetime.datetime.now()
            self.load()

        def __init_from_dict(self, obj):
            for i in obj["data"]:
                self.data.append(Nuvola.Event(i))
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])

        def load(self):
            e = self.parent.get("eventi-classe")
            self.data = []
            for i in e:
                self.data.append(Nuvola.Event(i))
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.refresh_time:
                self.load()

        def set_refresh_time(self, time):
            if type(time) is not datetime.timedelta:
                raise TypeError(time)
            self.refresh_time = time

        def get_all(self):
            self.check_and_update()
            for i in self.data:
                yield i

        def get_by_date(self, date):
            if type(date) is not date:
                raise TypeError(date)
            self.check_and_update()
            for i in self.data:
                if i.date_end >= date >= i.date_start:
                    yield i

        def get_by_teacher(self, teacher):
            self.check_and_update()
            for i in self.data:
                if i.teacher == teacher:
                    yield i

        def get_unseen(self):
            self.check_and_update()
            for i in self.data:
                if not i.seen:
                    yield i

        def get_by_type(self, type_):
            self.check_and_update()
            for i in self.data:
                if not i.type == type_:
                    yield i

        def get_by_id(self, id_):
            self.check_and_update()
            for i in self.data:
                if not i.id_ == id_:
                    return i

    class Event:
        ATTACHMENT_LINK = "/api-studente/v1/alunno/{}/aventi-classe/allegato/{}"

        def __init__(self, e):
            self.id_event = e["id"]
            self.type = e["tipo"]
            self.name = e["nome"]
            self.description = e["descrizione"]
            self.teacher = e["docente"]
            self.notes = e["annotazioni"]
            self.seen = e["visto"]
            self.attachments = [Nuvola.File(i, self.__class__) for i in e["allegati"]]
            self.video_link = e["linkVideo"]
            self.background_color = e["coloreSfondo"]
            self.text_color = e["coloreTesto"]
            self.border_color = e["coloreBordo"]
            self.id_notification = e["idNotifica"]
            self.date_start = datetime.datetime.fromisoformat(
                e["dataInizio"].replace("00:00:00", e["oraInizio"]+":00"))
            self.date_end = datetime.datetime.fromisoformat(
                e["dataFine"].replace("00:00:00", e["oraFine"] + ":00"))
            self.raw = e

    class TimeWindow:
        def __init__(self, parent, w, **kwargs):
            self.parent = parent
            self.id_ = w["id"]
            self.name = w["nome"]
            self.current = w["corrente"]
            self.raw = w
            self.refresh_time = datetime.timedelta(hours=6)
            if "old_data" in kwargs and type(kwargs["old_data"]) is dict:
                self.__init_from_dict(kwargs["old_data"])
                return
            self.mod_time = datetime.datetime.now()
            self.subjects = []
            self.load()

        def __init_from_dict(self, obj):
            self.subjects = [self.Subject(self, i["raw"], old_data=i["marks"]) for i in obj["subjects"]]
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])

        def load(self):
            s = self.parent.get("frazione-temporale/{}/voti/materie".format(self.id_))
            for i in s:
                self.subjects.append(self.Subject(self, i))
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.refresh_time:
                self.load()

        def set_refresh_time(self, time: datetime.timedelta):
            if type(time) is not datetime.timedelta:
                raise TypeError(time)
            self.refresh_time = time

        def get_subject_by_name(self, name):
            self.check_and_update()
            for i in self.subjects:
                if i.name == name:
                    return i

        def get_all_subjects(self):
            self.check_and_update()
            for i in self.subjects:
                yield i

        def get_subject_by_id(self, id_):
            self.check_and_update()
            for i in self.subjects:
                if i.id_ == id_:
                    return id_

        class Subject:
            def __init__(self, parent, s, **kwargs):
                self.parent = parent
                self.id_ = s["id"]
                self.name = s["materia"]
                self.type = s["tipo"]
                self.raw = s
                if "old_data" in kwargs and type(kwargs["old_data"]) is list:
                    self.__init_from_dict(kwargs["old_data"])
                    return
                self.marks = []
                self.load()

            def __init_from_dict(self, obj):
                self.marks = [self.Mark(i) for i in obj]

            def load(self):
                m = self.parent.parent.get(
                    "frazione-temporale/{}/voti/materia/{}".format(self.parent.id_, self.id_))
                for i in m[0]["voti"]:
                    self.marks.append(self.Mark(i))

            def get_all(self):
                self.parent.check_and_update()
                for i in self.marks:
                    yield i

            def get_by_teacher(self, teacher):
                self.parent.check_and_update()
                for i in self.marks:
                    if i.teacher == teacher:
                        yield i

            def get_by_date(self, date):
                if type(date) is not datetime.date:
                    raise TypeError(date)
                self.parent.check_and_update()
                for i in self.marks:
                    if i.date == date:
                        yield i

            def get_by_weight(self, min_, max_=1):
                self.parent.check_and_update()
                for i in self.marks:
                    if min_ <= i.weight <= max_:
                        yield i

            def get_by_relevance(self):
                self.parent.check_and_update()
                for i in self.marks:
                    if i.relevant:
                        yield i

            def get_by_type(self, type_):
                self.parent.check_and_update()
                for i in self.marks:
                    if i.type_ == type_:
                        yield i

            class Mark:
                def __init__(self, m):
                    self.date = datetime.datetime.fromisoformat(m["data"]).date()
                    self.teacher = m["docente"]
                    self.type_ = m["tipologia"]
                    self.mark_string = m["valutazione"]
                    self.mark = float(m["valutazioneMatematica"])
                    self.relevant = m["faMedia"]
                    self.weight = int(m["peso"][:-1]) / 100
                    self.description = m["descrizione"]
                    self.name_objective = m["nomeObiettivo"]
                    self.objectives = m["obiettivi"]
                    self.raw = m

    class Irregularity:
        ABSENCE = 0
        DELAY = 1
        EXIT = 2

        def __init__(self, a, parent):
            self.parent = parent
            self.id = a["id"]
            self.type = {
                "ASSENZA": self.ABSENCE,
                "RITARDO": self.DELAY,
                "USCITA": self.EXIT,
                "RITARDO/USCITA": self.DELAY | self.EXIT
            }[a["tipo"]]
            self.denomination = a["tipoAssenza"]
            self.shift = a["turno"]
            if not a["ora"]:
                self.lesson = None
            else:
                self.lesson = a["ora"]["numeroOra"]
            self.date = datetime.datetime.fromisoformat(a["data"]).date()
            self.justified = a["giustificata"]
            details = self.__get_details()
            self.details = details
            self.shift = details["turno"]
            self.timeEnter = details["orarioIngresso"]
            if not self.timeEnter:
                pass
            self.raw = a

        def __get_details(self):
            return self.parent.get_custom("/api-studente/v1/assenza/" + str(self.id))["dettaglio"]

    class File:
        def __init__(self, f, parent, **kwargs):
            if "old_data" in kwargs and type(kwargs["old_data"]) is dict:
                self.__init_from_dict(kwargs["old_data"])
                return
            self.parent = parent
            self.id_ = f["id"]
            self.name = f["nome"]
            self.mime_type = f["mimeType"]

        def __init_from_dict(self, obj):
            for i in obj:
                self.__setattr__(i, obj[i])

    def dump_to_dict(self, update_first=False):
        self.homeworks.check_and_update(update_first)
        self.events.check_and_update(update_first)
        for i in self.get_time_windows():
            i.check_and_update(update_first)

        output = {
            "homeworks": {
                "mod_time": self.homeworks.mod_time.timestamp(),
                "data": []
            },
            "events": {
                "mod_time": self.events.mod_time.timestamp(),
                "data": []
            },
            "timeWindows": [],
            "version": VERSION
        }

        # homeworks
        for h in self.homeworks.get_all():
            output["homeworks"]["data"].append(h.raw)

        # events
        for e in self.events.get_all():
            output["events"]["data"].append(e.raw)

        # timeWindow
        for tw in self.time_windows:
            t_tw = {
                "mod_time": tw.mod_time.timestamp(),
                "raw": tw.raw,
                "subjects": []
            }
            for s in tw.get_all_subjects():
                t_s = {
                    "raw": s.raw,
                    "marks": []
                }
                for m in s.marks:
                    t_s["marks"].append(m.raw)
                t_tw["subjects"].append(t_s)
            output["timeWindows"].append(t_tw)
        return output
