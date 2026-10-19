"""Authenticated sandbox checks; only read routes plus own login/logout session."""
import json
from pathlib import Path
import requests
from werkzeug.security import check_password_hash
from runtime_common import HERE, PRIOR, ROOT, NET, ORIGINAL, original, inspect, docker, rows, data_gate, digest


def main():
    deployment = json.loads((HERE / "deployment.json").read_text())
    assert deployment["status"] == "PASS"
    admin = inspect(deployment["admin_id"])
    assert admin["State"]["Health"]["Status"] == "healthy"
    assert admin["Image"] == deployment["image_id"]
    assert not admin["HostConfig"]["PortBindings"] and set(admin["NetworkSettings"]["Networks"]) == {NET}
    env = dict(v.split("=", 1) for v in admin["Config"]["Env"])
    old_env = dict(v.split("=", 1) for v in original("admin")["Config"]["Env"])
    assert env == old_env
    assert env["JOB_MODE"] == "request" and env["META_CLIENT_ID"] == "client_meta_sandbox"
    # Validate the existing configured credential against the stored hash BEFORE
    # sending one login attempt; never reset a password or forge a session.
    users = rows("SELECT email,password FROM users WHERE role='admin' AND active=1")
    account = next((u for u in users if u["email"] == env.get("INITIAL_ADMIN_EMAIL", "").strip().lower()), None)
    assert account and env.get("INITIAL_ADMIN_PASSWORD") and check_password_hash(account["password"], env["INITIAL_ADMIN_PASSWORD"]), "manual login required"
    base = "http://localhost:8191"
    session = requests.Session(); session.trust_env = False
    report = {"provider_calls": 0, "mutations": ["own login session", "own logout session"], "checks": {}}
    logged_in = False
    csrf = None
    headers = {"X-KDH-Request": "1", "Origin": base}
    try:
        assert session.get(base + "/health", timeout=5).status_code == 200
        assert session.get(base + "/", timeout=5).status_code == 200
        assert session.get(base + "/api/auth/me", timeout=5).json()["user"] is None
        login = session.post(base + "/api/auth/login", headers=headers,
            json={"email": account["email"], "password": env["INITIAL_ADMIN_PASSWORD"]}, timeout=10)
        assert login.status_code == 200
        logged_in = True
        csrf = login.json()["csrf"]
        cookie = login.headers["Set-Cookie"]
        assert env["ADMIN_SESSION_COOKIE_NAME"] + "=" in cookie
        assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Path=/" in cookie
        assert "Secure;" not in cookie  # approved localhost HTTP configuration
        assert session.get(base + "/api/auth/me", timeout=5).json()["user"]["role"] == "admin"
        assert session.post(base + "/api/auth/logout", headers=headers, json={}, timeout=5).status_code == 403
        bad_origin = dict(headers, Origin="http://example.invalid", **{"X-CSRF-Token": csrf})
        assert session.post(base + "/api/auth/logout", headers=bad_origin, json={}, timeout=5).status_code == 403
        report["checks"]["health_login_session_cookie_csrf_origin"] = "PASS"
        asset = "cff1f3d5e6f433e021850fbde5b1d3f3"
        period = "start=2026-09-19&end=2026-10-16"
        response = session.get(base + "/api/meta/reporting/kpis/" + asset + "?" + period, timeout=10)
        assert response.status_code == 200
        payload = response.json()
        assert payload["client_id"] == "client_meta_sandbox" and payload["asset_id"] == asset
        assert payload["data_origin"] == "persisted_unverified" and payload["verified"] is False and payload["publishable"] is False
        post = payload["metrics"]["facebook_content.posts_published"]
        interactions = payload["metrics"]["facebook_content.engagements"]
        assert post["summary"]["value"] == 14 and post["summary"]["coverage_days"] == 28
        assert interactions["summary"]["value"] is None and interactions["status"] == "no_data"
        assert payload["snapshot_metrics"] is None  # old snapshots stay old; no invented receipt
        (HERE / "content-kpi-response.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["checks"]["content_kpi"] = {"status": "PASS", "period_posts": 14, "page_coverage_days": 28,
            "period_engagement": None, "engagement_status": "no_data", "snapshot_metrics": None}
        preview = session.get(base + "/api/meta/reporting/preview?asset_id=" + asset + "&" + period, timeout=10)
        assert preview.status_code == 409 and preview.json()["code"] == "meta_contract_missing"
        report["checks"]["historical_source_guard"] = {"status": "PASS", "http_status": 409, "code": "meta_contract_missing"}
        viewer = session.get(base + "/api/internal/v1/viewer/report-bundles/phase5b-nonexistent?revision=1", timeout=5)
        assert viewer.status_code in (401, 403)
        report["checks"]["viewer_requires_backend_authorization"] = {"status": "PASS", "http_status": viewer.status_code}
        for path in ("static/app.js", "static/meta_reporting_ui.js", "static/views.js"):
            response = session.get(base + "/" + path, timeout=5)
            assert response.status_code == 200 and digest(response.content) == digest((ROOT / path).read_bytes())
        report["checks"]["served_ui_hashes_match_manifest"] = "PASS"
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error_type"] = type(error).__name__
        raise
    finally:
        if logged_in and csrf:
            response = session.post(base + "/api/auth/logout", headers=dict(headers, **{"X-CSRF-Token": csrf}), json={}, timeout=5)
            assert response.status_code == 200
            assert session.get(base + "/api/auth/me", timeout=5).json()["user"] is None
            report["checks"]["own_session_logout"] = "PASS"
        (HERE / "http-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    data_gate("data-after-http.json")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("HTTP VERIFICATION BLOCKED: " + type(error).__name__ + "; sensitive details withheld")
        raise SystemExit(1)
