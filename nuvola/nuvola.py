import datetime
import json
from copy import deepcopy
from getpass import getpass
from http.client import HTTPSConnection
from .scraper import scrape_from_credentials, scrape_from_token, ExpiredSessionTokenException
from .version import VERSION
from os import access as os_access, W_OK
from os.path import isdir


class NuvolaOptions:
    DATA_TYPES = {
        "credentials": dict,
        "verbose": bool,
        "refresh_interval": datetime.timedelta,
        "start_date": datetime.date,
        "force_import": bool,
        "use_token_files": bool,
        "token_files_path": str,
        "homeworks": {
            "max_empty_days": int,
            "backwards_refresh_date": datetime.timedelta
        },
        "timeWindows": {
            "backwards_refresh_date": datetime.timedelta
        },
        "events": {
            "backwards_refresh_date": datetime.timedelta
        },
        "topics": {
            "max_empty_days": int,
            "backwards_refresh_date": datetime.timedelta
        }
    }

    def __init__(self, data=None):
        if data:
            self.data = data
        else:
            self.data = {
                "credentials": None,
                "verbose": False,
                "force_import": False,
                "refresh_interval": datetime.timedelta(hours=6),
                "start_date": datetime.date(year=2020, month=9, day=1),
                "use_token_files": True,
                "token_files_path": "",
                "homeworks": {
                    "max_empty_days": 15 * 4,
                    "backwards_refresh_date": datetime.timedelta(hours=24)
                },
                "topics": {
                    "max_empty_days": 15 * 4,
                    "backwards_refresh_date": datetime.timedelta(days=7)
                }
            }

    def set(self, key, value):
        if key == "token_files_path":
            if not isdir(value):
                raise FileNotFoundError
            elif not os_access(value, W_OK):
                raise PermissionError
            if value and value[-1] != "/":
                value += "/"

        if type(value) is self.DATA_TYPES[key]:
            self.data[key] = value
        elif type(value) is dict:
            for i in value:
                if type(value[i]) is self.DATA_TYPES[key][i]:
                    self.data[key] = value
                else:
                    raise TypeError(f"Invalid type: \"{self.DATA_TYPES[key][i]}\" required, \"{type(value[i])}\" provided")
        else:
            raise TypeError(f"Invalid type: \"{self.DATA_TYPES[key]}\" required, \"{type(value)}\" provided")

    def get(self, key):
        try:
            return self.data[key]
        except KeyError:
            raise self.KeyNotFoundException(f"The provided key (\"{key}\") can't be found.")

    def keys(self):
        return self.data.keys()

    class KeyNotFoundException(Exception):
        pass


class Nuvola:
    def __init__(self, id_student, options=NuvolaOptions(), old_data=None):
        """
        :param id_student: Student id, for now it can only be retrieved with a browser, sadly.
        :param options: User defined options
        :type id_student: int
        :type options: NuvolaOptions
        """

        def __init(self_, obj=None):
            if obj is None:
                obj = {
                    "homeworks": None,
                    "events": None,
                    "topics": None,
                    "timeWindows": None
                }
            self_.print(":: Init :: Homeworks...", end="")
            timer_ = datetime.datetime.now()
            self_.homeworks = self_.Homeworks(self_, self_.options, obj["homeworks"])
            self_.print(" OK ({} seconds)".format((datetime.datetime.now() - timer_).total_seconds()))
            self_.print(":: Init :: Events...", end="")
            timer_ = datetime.datetime.now()
            self_.events = self_.Events(self_, self_.options, obj["events"])
            self_.print(" OK ({} seconds)".format((datetime.datetime.now() - timer_).total_seconds()))
            self_.print(":: Init :: Topics...", end="")
            timer_ = datetime.datetime.now()
            self_.topics = self_.Topics(self_, self_.options, obj["topics"])
            self_.print(" OK ({} seconds)".format((datetime.datetime.now() - timer_).total_seconds()))
            self_.print(":: Init :: TimeWindows...", end="")
            timer_ = datetime.datetime.now()
            self_.time_windows = self_.__load_time_windows(obj["timeWindows"])
            self_.print(" OK ({} seconds)".format((datetime.datetime.now() - timer_).total_seconds()))
            self_.active_time_window = self_.__select_best_time_window()

        self.id_student = id_student
        self.options = options
        timer = datetime.datetime.now()
        self.print(":: Init :: Connection...", end="")
        self.conn = self.Connection(self, self.options)
        self.print(" OK ({} seconds)".format((datetime.datetime.now() - timer).total_seconds()))
        self.homeworks, self.events, self.topics, self.time_windows, self.active_time_window = (
            None, None, None, None, None)

        if type(old_data) is dict:
            if all([i in ("homeworks", "events", "timeWindows", "version", "topics") for i in old_data.keys()]):
                if self.options.get("force_import") or old_data["version"] == VERSION or input(
                        "Trying to import data from another version of nuvola, continue? (y,N) ") == "y":
                    __init(self, old_data)
                    return
            else:
                self.print(":: Import :: Import object format is not accepted, skipping import")
        __init(self)

    def print(self, data, end="\n"):
        """
        Prints data only when verbose is active

        :param data: Data to be print
        :param end: String at the end of data, default: newline
        """
        if self.options.get("verbose"):
            print(data, end=end)

    def get(self, call):
        """
        Formats api request and sends it to /api-studente/v1/alunno/[call]

        :param call: API call
        :type call: str
        :return: dict
        """
        url = "/api-studente/v1/alunno/{}/{}".format(self.id_student, call)
        d = self.conn.get_data(url)
        return d["valori"]

    def get_custom(self, custom_url):
        """
        Send raw call to connection.get_data without formatting to nuvola.madisoft.it/[custom_url].

        :param custom_url: URL
        :type custom_url: str
        :return: dict
        """
        d = self.conn.get_data(custom_url)
        return d

    def __load_time_windows(self, old_data=None):
        """
        :param old_data:
        :type old_data: dict
        :rtype: list
        """
        if type(old_data) is list:
            return [self.TimeWindow(self, i["raw"], self.options, i) for i in old_data]
        return [self.TimeWindow(self, i, self.options) for i in self.get("frazioni-temporali")]

    def __load_irregularities(self):
        """
        :rtype: list
        """
        return [self.Irregularity(i, self) for i in self.get("assenze")]

    def get_time_windows(self):
        """
        Get all available time windows
        """
        for i in self.time_windows:
            yield i

    def check_and_update_all(self, force=False):
        h = [self.homeworks, self.events, self.topics, self.events]
        for i in self.time_windows:
            h.append(i)
        for i in h:
            i.check_and_update(force)

    class Connection:
        class RequestErrorException(Exception):
            pass

        def __init__(self, parent, options):
            """
            :param parent: Parent nuvola object
            :type parent: Nuvola
            """
            self.parent = parent
            self.options = options
            self.c = HTTPSConnection("nuvola.madisoft.it")
            self.s_token = None
            self.s_token = None
            if self.options.get("use_token_files"):
                try:
                    with open(f"{self.options.get('token_files_path')}s.tok", "r") as f:
                        self.s_token = f.read()
                except FileNotFoundError:
                    self.refresh_tokens()
                    return
                try:
                    with open(f"{self.options.get('token_files_path')}u.tok", "r") as f:
                        self.u_token = f.read()
                except FileNotFoundError:
                    self.refresh_tokens()

            else:
                self.refresh_tokens()

        def refresh_tokens(self):
            try:
                self.u_token = scrape_from_token(self.s_token, self.options.get("verbose"))
            except ExpiredSessionTokenException:
                if self.options.get("credentials") is not None:
                    self.s_token, self.u_token = scrape_from_credentials(
                        self.options.get("credentials")["username"], self.options.get("credentials")["password"],
                        self.options.get("verbose"))
                else:
                    self.parent.print(":: Connection :: Expired session token, please use credentials")
                    self.s_token, self.u_token = scrape_from_credentials(
                        input("Username: "), getpass("Password: "), self.options.get("verbose"))
            if self.options.get("use_token_files"):
                with open(f"{self.options.get('token_files_path')}s.tok", "w") as fs, \
                        open(f"{self.options.get('token_files_path')}u.tok", "w") as fu:
                    fs.write(self.s_token)
                    fu.write(self.u_token)

        def get_data(self, url):
            self.c.request("GET", url, headers={"Authorization": "Bearer " + self.u_token})
            j_r = self.c.getresponse()
            j = json.load(j_r)
            if j == "Errore":
                raise self.RequestErrorException(j)
            if "code" in j and j["code"] == 401:
                self.parent.print(":: Connection :: Token expired, getting a new one...")
                self.refresh_tokens()
                return self.get_data(url)
            else:
                return j

        def makefile(self, file):
            """

            :param file: File to be read
            :return: Seekable file-type object
            :rtype: Nuvola.File
            """
            if type(file) is not Nuvola.File:
                raise TypeError(file)
            self.c.request("GET",
                           f"https://nuvola.madisoft.it/"
                           f"{file.parent.ATTACHMENT_LINK.format(self.parent.id_student, file.id_)}",
                           headers={"Authorization": "Bearer " + self.u_token})
            return self.c.getresponse()

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
        def __init__(self, parent, options, old_data=None):
            """
            :param parent: Parent nuvola object
            :param options: Options object
            :type parent: Nuvola
            :type options: NuvolaOptions
            """
            self.parent = parent
            self.options = options
            self.data = []
            self.furthest_homework = None
            if type(old_data) is dict:
                self.__init_from_dict(old_data)
                return
            self.mod_time = datetime.datetime.fromtimestamp(0)
            self.load()

        def __init_from_dict(self, obj):
            for i in obj["data"]:
                self.data.append(Nuvola.Homework(i))
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])
            for i in self.data:
                if self.furthest_homework is None or i.date_expired > self.furthest_homework.date_expired:
                    self.furthest_homework = i

        def load(self):
            empty_count = 0
            if self.data:
                expired = list(self.get_by_expiration_date(
                    datetime.date.today() - self.options.get("homeworks")["backwards_refresh_date"],
                    self.options.get("homeworks")["backwards_refresh_date"] + (
                            self.furthest_homework.date_expired - datetime.date.today()), True))
                for i in expired:
                    self.data.remove(i)
                date_s = datetime.date.today() - self.options.get("homeworks")["backwards_refresh_date"]
            else:
                date_s = self.options.get("start_date") + datetime.timedelta(days=1)

            date_e = date_s + datetime.timedelta(days=15)
            while True:
                # for each iteration we ask nuvola homeworks in a period of time of 15 days
                # the iteration stops when the number of consequent days without homeworks reaches max_empty_days
                c = self.parent.get("compito/elenco/{}/{}".format(
                    date_s.strftime("%d-%m-%Y"), date_e.strftime("%d-%m-%Y")))
                if len(c) == 0:
                    empty_count += 1
                else:
                    to_add = [Nuvola.Homework(i) for i in c]
                    self.data += to_add
                    for i in to_add:
                        if self.furthest_homework is None or i.date_expired > self.furthest_homework.date_expired:
                            self.furthest_homework = i
                    empty_count = 0
                if empty_count >= self.options.get("homeworks")["max_empty_days"] / 15:
                    break
                date_s = date_e + datetime.timedelta(days=1)
                date_e += datetime.timedelta(days=15)
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.options.get("refresh_interval"):
                self.parent.print(":: Fetch :: Homeworks...", end="")
                self.load()
                self.parent.print(" OK")

        def get_by_assignment_date(self, date, interval=datetime.timedelta(days=0)):
            self.check_and_update()
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if date + interval >= i.date_assigned >= date:
                    yield i


        def get_by_expiration_date(self, date, interval=datetime.timedelta(days=0), skip_check=False):
            if not skip_check:
                self.check_and_update()
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if date + interval >= i.date_expired >= date:
                    yield i

        def get_by_subject(self, subject, search=False):
            self.check_and_update()
            for i in self.data:
                if i.subject == subject or search and subject in i.subject:
                    yield i

        def get_all(self):
            self.check_and_update()
            for i in self.data:
                yield i

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
        def __init__(self, parent, options, old_data=None):
            self.parent = parent
            self.options = options
            self.data = []
            if type(old_data) is dict:
                self.__init_from_dict(old_data)
                return
            self.mod_time = datetime.datetime.fromtimestamp(0)
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
            if force or datetime.datetime.now() > self.mod_time + self.options.get("refresh_interval"):
                self.parent.print(":: Fetch :: Events...", end="")
                self.load()
                self.parent.print(" OK")

        def get_all(self):
            self.check_and_update()
            for i in self.data:
                yield i

        def get_by_date(self, date, interval=datetime.timedelta(days=0)):
            if type(date) is not datetime.date:
                raise TypeError(date)
            self.check_and_update()
            for i in self.data:
                if i.date_start <= date <= i.date_end or i.date_start <= date + interval <= i.date_end:
                    yield i

        def get_if_occurring(self, date):
            if type(date) is not datetime.date:
                raise TypeError(date)
            self.check_and_update()
            for i in self.data:
                if i.date_start <= date <= i.date_end:
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
                if i.id_ == id_:
                    return i

    class Event:
        ATTACHMENT_LINK = "/api-studente/v1/alunno/{}/eventi-classe/allegato/{}"

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
                e["dataInizio"].replace("00:00:00", e["oraInizio"] + ":00"))
            self.date_end = datetime.datetime.fromisoformat(
                e["dataFine"].replace("00:00:00", e["oraFine"] + ":00"))
            self.raw = e

    class TimeWindow:
        def __init__(self, parent, w, options, old_data=None):
            self.parent = parent
            self.id_ = w["id"]
            self.name = w["nome"]
            self.current = w["corrente"]
            self.raw = w
            self.options = options
            if type(old_data) is dict:
                self.__init_from_dict(old_data)
                return
            self.mod_time = datetime.datetime.fromtimestamp(0)
            self.subjects = []
            self.load()

        def __init_from_dict(self, obj):
            self.subjects = [self.Subject(self, i["raw"], i["marks"]) for i in obj["subjects"]]
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])

        def load(self):
            self.subjects = []
            s = self.parent.get("frazione-temporale/{}/voti/materie".format(self.id_))
            for i in s:
                self.subjects.append(self.Subject(self, i))
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.options.get("refresh_interval"):
                self.parent.print(":: Fetch :: TimeWindow...", end="")
                self.load()
                self.parent.print(" OK")

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
                    return i

        class Subject:
            def __init__(self, parent, s, old_data=None):
                self.parent = parent
                self.id_ = s["id"]
                self.name = s["materia"]
                self.type = s["tipo"]
                self.raw = s
                if type(old_data) is list:
                    self.__init_from_dict(old_data)
                    return
                self.marks = []
                self.load()

            def __init_from_dict(self, obj):
                self.marks = [self.Mark(i, self) for i in obj]

            def load(self):
                self.marks = []
                m = self.parent.parent.get(
                    "frazione-temporale/{}/voti/materia/{}".format(self.parent.id_, self.id_))
                for i in m[0]["voti"]:
                    self.marks.append(self.Mark(i, self))

            def get_all(self):
                self.parent.check_and_update()
                for i in self.marks:
                    yield i

            def get_by_teacher(self, teacher):
                self.parent.check_and_update()
                for i in self.marks:
                    if i.teacher == teacher:
                        yield i

            def get_by_date(self, date, interval=datetime.timedelta(days=0)):
                if type(date) is not datetime.date:
                    raise TypeError(date)
                self.parent.check_and_update()
                for i in self.marks:
                    if date <= i.date <= date + interval:
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
                def __init__(self, m, parent):
                    self.parent = parent
                    self.subject = self.parent.name
                    self.subject_id = self.parent.id_
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

    class Topics:
        def __init__(self, parent, options, old_data=None):
            self.parent = parent
            self.options = options
            self.data = []
            if type(old_data) is dict:
                self.__init_from_dict(old_data)
                return
            self.mod_time = datetime.datetime.fromtimestamp(0)
            self.load()

        def __init_from_dict(self, obj):
            for i in obj["data"]:
                self.data.append(Nuvola.Topic(i["lesson"], i["lesson"]["argomenti"], i["class"], i["class_id"]))
            self.mod_time = datetime.datetime.fromtimestamp(obj["mod_time"])

        def load(self):
            if self.data:
                expired = list(self.get_by_date(
                    datetime.date.today() - self.options.get("topics")["backwards_refresh_date"],
                    self.options.get("topics")["backwards_refresh_date"], True))
                for i in range(len(expired)):
                    self.data.remove(expired[i])
                date_s = datetime.date.today() + datetime.timedelta(days=1) - self.options.get(
                    "topics")["backwards_refresh_date"]
            else:
                date_s = self.options.get("start_date") + datetime.timedelta(days=1)
            date_e = date_s + datetime.timedelta(days=15)
            empty_count = 0

            while True:
                # for each iteration we ask nuvola homeworks in a period of time of 15 days
                c = self.parent.get("argomento-lezione/elenco/{}/{}".format(
                    date_s.strftime("%d-%m-%Y"), date_e.strftime("%d-%m-%Y")))
                emp = True
                for i in c:
                    for j in i["ore"]:
                        if j["argomenti"]:
                            emp = False
                            if len(j["argomenti"]) == 1:
                                self.data.append(Nuvola.Topic(j, j["argomenti"][0], i["classe"], i["classeId"]))
                            else:
                                for k in range(len(j["argomenti"])):
                                    self.data.append(Nuvola.Topic(j, j["argomenti"][k], i["classe"], i["classeId"]))
                if emp:
                    empty_count += 1
                if empty_count >= self.options.get("topics")["max_empty_days"] / 15:
                    break
                date_s = date_e + datetime.timedelta(days=1)
                date_e += datetime.timedelta(days=15)
            self.mod_time = datetime.datetime.now()

        def check_and_update(self, force=False):
            if force or datetime.datetime.now() > self.mod_time + self.options.get("refresh_interval"):
                self.parent.print(":: Fetch :: Topics...", end="")
                self.load()
                self.parent.print(" OK")

        def get_all(self):
            self.check_and_update()
            for i in self.data:
                yield i

        def get_by_date(self, date, interval=datetime.timedelta(days=0), skip_check=False):
            if type(date) is not datetime.date:
                raise TypeError(date)
            if not skip_check:
                self.check_and_update()
            for i in self.data:
                if date <= i.date <= date + interval:
                    yield i

        def get_by_teacher(self, teacher):
            self.check_and_update()
            for i in self.data:
                if i.teacher == teacher:
                    yield i

        def get_by_subject(self, subject, search=False):
            self.check_and_update()
            for i in self.data:
                if i.subject == subject or search and subject in i.subject:
                    yield i

        def get_by_type(self, type_):
            self.check_and_update()
            for i in self.data:
                if not i.type == type_:
                    yield i

        def get_by_id(self, id_):
            self.check_and_update()
            for i in self.data:
                if i.id_ == id_:
                    return i

    class Topic:
        def __init__(self, t, a, class_, class_id):
            self.class_ = class_
            self.class_id = class_id

            self.lesson = t["numeroOra"]
            self.time_start = datetime.datetime.fromisoformat(
                t["giorno"].replace("00:00:00", t["inizioOra"] + ":00")).time()
            self.time_end = datetime.datetime.fromisoformat(
                t["giorno"].replace("00:00:00", t["fineOra"] + ":00")).time()
            self.date = datetime.datetime.fromisoformat(t["giorno"]).date()

            self.id_ = a["id"]
            self.type = a["tipo"]
            self.subject = a["materia"]
            self.name = a["nomeArgomento"]
            self.long_description = a["descrizioneEstesa"]
            self.co_presence = a["compresenza"]
            self.teacher = a["docente"]
            self.notes = a["annotazioni"]
            self.attachments = [Nuvola.File(i, self.__class__) for i in a["allegati"]]
            self.youtube_link = a["video_youtube"]
            t_r = deepcopy(t)
            t_r["argomenti"] = deepcopy(a)
            self.raw = t_r

    class File:
        def __init__(self, f, parent, old_data=None):
            if type(old_data) is dict:
                self.__init_from_dict(old_data)
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
        self.topics.check_and_update(update_first)

        output = {
            "homeworks": {
                "mod_time": self.homeworks.mod_time.timestamp(),
                "data": []
            },
            "events": {
                "mod_time": self.events.mod_time.timestamp(),
                "data": []
            },
            "topics": {
                "mod_time": self.topics.mod_time.timestamp(),
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

        # topics
        for t in self.topics.get_all():
            output["topics"]["data"].append({
                "lesson": t.raw,
                "class": t.class_,
                "class_id": t.class_id
            })
        return output

    class IncompatibleTimeWindowException(Exception):
        pass

    class MissingSuitableTimeWindowException(Exception):
        pass
