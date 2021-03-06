import seleniumwire.webdriver
import requests
from json.decoder import JSONDecodeError
from simplejson.decoder import JSONDecodeError as JSONDecodeError_

opt = seleniumwire.webdriver.ChromeOptions()
opt.headless = True


class InvalidCredentialsException(Exception):
    pass


class ExpiredSessionTokenException(Exception):
    pass


class GenericErrorException(Exception):
    pass


def scrape_from_token(session_token):
    try:
        return requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                   cookies={"nuvola": str(session_token)}).json()["token"]
    except (JSONDecodeError, JSONDecodeError_):
        raise ExpiredSessionTokenException


def scrape_from_credentials(user, pwd):
    d = seleniumwire.webdriver.Chrome(chrome_options=opt)
    d.get("https://nuvola.madisoft.it/login/")
    d.find_element_by_id("username").send_keys(user)
    d.find_element_by_id("password").send_keys(pwd)
    d.find_elements_by_tag_name("button")[1].click()
    if "https://nuvola.madisoft.it/area-studente" not in [i.url for i in d.requests]:
        raise InvalidCredentialsException
    session_token = d.get_cookie("nuvola")["value"]
    d.close()

    try:
        r = requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                         cookies={"nuvola": str(session_token)})
        return session_token, r.json()["token"]
    except JSONDecodeError:
        raise InvalidCredentialsException(r.text)
