import pytest
import subprocess
import datetime
import os
from pymongo import MongoClient

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        extra = getattr(report, "extra", [])
        report.description = str(item.function.__doc__)
        if hasattr(pytest, "data_log"):
            if not hasattr(pytest, "results"):
                pytest.results = []
                pytest.job_info = {}
                githash = subprocess.check_output("git rev-parse HEAD", shell=True)
                pytest.job_info["githash"] = githash.decode("utf-8").strip()
                pytest.job_info["start_time"] = str(datetime.datetime.now())

            pytest.results.append(
                {
                    "name": report.head_line,
                    "data_log": pytest.data_log,
                    "report": report._to_json(),
                }
            )
        else:
            print("log data found")


def pytest_sessionfinish(session, exitstatus):
    print("\n\n\n\n\n")
    print("Session finished, collecting logs for database")

    db_ip = os.getenv("DATABASE_IP")
    if not db_ip:
        db_ip = "spock"
    db_port = os.getenv("DATABASE_PORT")
    if not db_port:
        db_port = 27017
    db_name = os.getenv("COLLECTION_NAME")
    if not db_name:
        if hasattr(pytest, "collection_name"):
            db_name = pytest.collection_name
        else:
            db_name = "scratch"

    client = MongoClient(db_ip, int(db_port))
    db = client["jif_testing"]
    collection = db[db_name]
    collection.insert_one(
        {
            "testname": pytest.testname,
            "job_info": pytest.job_info,
            "results": pytest.results,
        }
    )
