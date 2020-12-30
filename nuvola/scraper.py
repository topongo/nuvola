import seleniumwire.webdriver
from requests import get
from json.decoder import JSONDecodeError

opt = seleniumwire.webdriver.ChromeOptions()
opt.headless = False


class InvalidCredentialsException(Exception):
    pass


class ExpiredSessionTokenException(Exception):
    pass


def scrape_from_token(session_token):
    try:
        return get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                   cookies={"nuvola": str(session_token)}).json()["token"]
    except JSONDecodeError:
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

    try:
        return session_token, get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                                  cookies={"nuvola": str(session_token)}).json()["token"]
    except JSONDecodeError:
        raise InvalidCredentialsException
