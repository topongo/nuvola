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


def scrape_from_token(session_token, verb=False):
    try:
        if verb:
            print(":: Scraper :: Trying to get auth_token...")
        return requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                   cookies={"nuvola": str(session_token)}).json()["token"]
    except (JSONDecodeError, JSONDecodeError_):
        if verb:
            print(":: Scraper :: Failed to get auth_token: session_token is not invalid.")
        raise ExpiredSessionTokenException


def scrape_from_credentials(user, pwd, verb=False):
    if verb:
        print(":: Scraper :: Starting driver...")
    d = seleniumwire.webdriver.Chrome(chrome_options=opt)
    if verb:
        print(":: Scraper :: Getting login page...")
    d.get("https://nuvola.madisoft.it/login/")
    d.find_element_by_id("username").send_keys(user)
    d.find_element_by_id("password").send_keys(pwd)
    d.find_elements_by_tag_name("button")[1].click()
    if verb:
        print(":: Scraper :: Logging in...")
    if "https://nuvola.madisoft.it/area-studente" not in [i.url for i in d.requests]:
        if verb:
            print(":: Scraper :: Login failed.")
        raise InvalidCredentialsException

    if verb:
        print(":: Scraper :: Authentication successful.")
    session_token = d.get_cookie("nuvola")["value"]
    d.close()

    try:
        if verb:
            print(":: Scraper :: Trying to get auth_token...")
        r = requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                         cookies={"nuvola": str(session_token)})
        return session_token, r.json()["token"]
    except (JSONDecodeError, JSONDecodeError_):
        if verb:
            print(":: Scraper :: Something has gone wrong.")
        raise InvalidCredentialsException
