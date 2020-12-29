import seleniumwire.webdriver
from requests import get

opt = seleniumwire.webdriver.ChromeOptions()
opt.headless = True


class InvalidCredentialsException(Exception):
    pass


class ExpiredSessionTokenException(Exception):
    pass


def scrape_from_token(session_token):
    try:
        return get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                   cookie={"Authorization": session_token}).json()["token"]
    except KeyError:
        raise ExpiredSessionTokenException


def scrape_from_credentials(user, pwd):
    d = seleniumwire.webdriver.Chrome(chrome_options=opt)
    d.get("https://nuvola.madisoft.it/login/")
    d.find_element_by_id("username").send_keys(user)
    d.find_element_by_id("password").send_keys(pwd)
    d.find_elements_by_tag_name("button")[0].click()
    if d.current_url == "https://nuvola.madisoft.it/login":
        raise InvalidCredentialsException
    session_token = d.get_cookie("nuvola")

    try:
        return session_token, get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                                  cookie={"Authorization": session_token}).json()["token"]
    except KeyError:
        raise InvalidCredentialsException
