from app.models import SystemConfig


def test_auth_options_tolerates_invalid_promo_center_numeric_values(client, db_session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="promo_center",
            config_value={
                "enabled": True,
                "schema_version": "abc",
                "invite_reward_points": "oops",
                "nav_cards": [
                    {
                        "key": "invite",
                        "sort_order": "bad-order",
                    }
                ],
                "reward_rules": {
                    "invite": {
                        "invitee_bind_reward_points": "bad-points",
                        "inviter_valid_invite_reward_points": "bad-points-2",
                    }
                },
            },
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/auth/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["promo_center"]["schema_version"] == 2
    assert data["promo_center"]["invite_reward_points"] == 2000
    assert data["promo_center"]["nav_cards"][0]["sort_order"] == 1
    assert data["promo_center"]["reward_rules"]["invite"]["invitee_bind_reward_points"] == 2000
    assert data["promo_center"]["reward_rules"]["invite"]["inviter_valid_invite_reward_points"] == 1000
