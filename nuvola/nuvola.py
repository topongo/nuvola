import datetime
import json
from getpass import getpass
from http.client import HTTPSConnection
from .scraper import scrape_from_credentials, scrape_from_token, ExpiredSessionTokenException


class Nuvola:
    def __init__(self, id_student, max_hw_int=15*4):
        self.conn = self.Connection()
        self.__update_homeworks()
        self.id_student = id_student
        self.max_homework_interval = max_hw_int

    def get(self, area):
        url = "/api-studente/v1/alunno/{}/{}".format(self.id_student, area)
        d = self.conn.get_data(url)
        return d["valori"]

    def get_custom(self, custom_url):
        d = self.conn.get_data(custom_url)
        return d

    def get_time_windows(self):
        return [self.TimeWindow(i) for i in self.get("frazioni-temporali")]

    def get_irregularities(self):
        return [self.Irregularity(i, self) for i in self.get("assenze")]

    def __update_homeworks(self):
        date_s = datetime.date(year=2020, month=9, day=1) + datetime.timedelta(days=1)
        date_e = date_s + datetime.timedelta(days=15)
        empty_count = 0
        o = []
        while True:
            # for each iteration we ask nuvola homeworks in a period of time of 15 days
            c = self.get_custom("/api-studente/v1/alunno/{}/compito/elenco/{}/{}".format(
                self.id_student, date_s.strftime("%d-%m-%Y"), date_e.strftime("%d-%m-%Y")))
            if "dettaglio" in c:
                print("Error getting homeworks:", c["dettaglio"])
            if len(c["valori"]) == 0:
                empty_count += 1
            else:
                o += c["valori"]
                empty_count = 0
            if empty_count >= self.max_homework_interval/15:
                break

            date_s = date_e + datetime.timedelta(days=1)
            date_e += datetime.timedelta(days=15)
        self.homeworks = self.Homeworks(o)

    class Homeworks:
        def __init__(self, hs):
            self.data = [Nuvola.Homework(h) for h in hs]

        def get_by_assignment_date(self, date):
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if i.date_assigned == date:
                    yield i

        def get_by_expiration_date(self, date):
            if type(date) is not datetime.date:
                raise TypeError(date)
            for i in self.data:
                if i.date_expired == date:
                    yield i

        def get_all(self):
            for i in self.data:
                yield i

    class Homework:
        def __init__(self, h):
            self.teacher = h["docente"]
            self.subject = h["materia"]
            self.attachments = [Nuvola.File(i) for i in h["allegati"]]
            self.class_ = h["classe"]
            self.class_id = h["classeId"]
            self.date_assigned = datetime.date.fromisoformat(h["dataAssegnazione"][:10])
            self.date_expired = datetime.date.fromisoformat(h["dataConsegna"][:10])
            self.description = h["descrizioneCompito"][0]
            self.raw = h

    class Connection:
        class RequestErrorException(Exception):
            pass

        def __init__(self):
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
                raise self.RequestErrorException(url)
            if "code" in j and j["code"] == 401:
                print("Token expired, getting a new one...")
                self.refresh_tokens()
                return self.get_data(url)
            else:
                return j

    class TimeWindow:
        def __init__(self, w):
            self.id = w["id"]
            self.name = w["nome"]
            self.current = w["corrente"]

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
        def __init__(self, f):
            self.id = f["id"]
            self.name = f["nome"]
            self.mime_type = f["mimeType"]

        def get_link(self):
            # todo: write this (get_link)
            pass