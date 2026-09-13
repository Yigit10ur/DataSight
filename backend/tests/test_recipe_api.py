from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ORDERS = b"city,product,revenue,cost\n" + b"".join(
    (
        f"{city},{product},{100 + index * 37},{50 + index * 11}\n".encode()
        for index, (city, product) in enumerate(
            [("Ankara", "A"), ("Izmir", "B"), ("Bursa", "A"), ("Izmir", "C")] * 10
        )
    )
)

GAPPED = b"city,revenue\nAnkara,100\nIzmir,\nAnkara,300\n"


def upload(content: bytes = ORDERS, name: str = "orders.csv") -> str:
    response = client.post("/api/upload", files={"file": (name, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["dataset_id"]


def preview(dataset_id: str, steps: list[dict], limit: int | None = None) -> dict:
    url = f"/api/datasets/{dataset_id}/recipe/preview"
    if limit is not None:
        url = f"{url}?limit={limit}"
    response = client.post(url, json={"steps": steps})
    assert response.status_code == 200, response.text
    return response.json()


def apply(dataset_id: str, steps: list[dict]):
    return client.post(f"/api/datasets/{dataset_id}/recipe/apply", json={"steps": steps})


TOP_CITIES = [
    {
        "op": "aggregate",
        "group_by": ["city"],
        "aggregations": [{"function": "sum", "column": "revenue"}],
    },
    {"op": "sort_rows", "columns": ["sum_revenue"], "order": "desc"},
    {"op": "limit_rows", "count": 2},
]


def test_preview_runs_the_recipe_and_reports_each_step():
    dataset_id = upload()
    body = preview(dataset_id, TOP_CITIES)

    assert body["refusal"] is None
    assert body["source_rows"] == 40
    assert body["preview"]["total_rows"] == 2
    assert body["preview"]["columns"] == ["city", "sum_revenue"]
    assert [report["op"] for report in body["reports"]] == [
        "aggregate",
        "sort_rows",
        "limit_rows",
    ]
    assert [report["rows_out"] for report in body["reports"]] == [3, 3, 2]


def test_preview_hands_back_the_projected_schema_for_columns_the_file_never_had():
    dataset_id = upload()
    body = preview(
        dataset_id,
        [
            {
                "op": "derive_column",
                "name": "margin",
                "expression": {
                    "kind": "arithmetic",
                    "left": {"kind": "column", "name": "revenue"},
                    "operator": "subtract",
                    "right": {"kind": "column", "name": "cost"},
                },
            }
        ],
    )

    projected = {column["name"]: column["inferred_type"] for column in body["columns"]}
    assert projected["margin"] == "numeric"


def test_preview_stores_nothing():
    dataset_id = upload()
    preview(dataset_id, TOP_CITIES)

    # The source is untouched and no new dataset was made to hold the result.
    assert client.get(f"/api/datasets/{dataset_id}/profile").json()["rows"] == 40
    assert len(client.get(f"/api/datasets/{dataset_id}/lineage").json()["chain"]) == 1


def test_a_refused_step_comes_back_as_a_normal_answer_with_what_ran_before_it():
    dataset_id = upload()
    body = preview(
        dataset_id,
        [
            {"op": "select_columns", "columns": ["city", "revenue"]},
            {"op": "sort_rows", "columns": ["margin"]},
        ],
    )

    assert body["refusal"]["step_index"] == 1
    assert "margin" in body["refusal"]["reason"]
    # The rows the accepted step left are still there to look at.
    assert body["preview"]["columns"] == ["city", "revenue"]
    assert len(body["reports"]) == 1


def test_applying_a_recipe_answers_with_a_profile_like_an_upload_does():
    dataset_id = upload()
    response = apply(dataset_id, TOP_CITIES)

    assert response.status_code == 200
    profile = response.json()
    assert profile["dataset_id"] != dataset_id
    assert profile["rows"] == 2
    assert profile["columns"] == 2
    assert profile["filename"] == "orders.csv (3 steps)"


def test_everything_the_dashboard_asks_for_works_on_a_derived_dataset():
    """The whole reason a recipe's result becomes a dataset rather than a table."""
    dataset_id = upload()
    derived_id = apply(
        dataset_id,
        [
            {
                "op": "filter_rows",
                "clauses": [{"column": "revenue", "operator": "gt", "value": 200}],
            },
            {
                "op": "derive_column",
                "name": "margin",
                "expression": {
                    "kind": "arithmetic",
                    "left": {"kind": "column", "name": "revenue"},
                    "operator": "subtract",
                    "right": {"kind": "column", "name": "cost"},
                },
            },
        ],
    ).json()["dataset_id"]

    for endpoint in ("profile", "preview", "analysis", "charts", "quality", "insights"):
        response = client.get(f"/api/datasets/{derived_id}/{endpoint}")
        assert response.status_code == 200, f"{endpoint}: {response.text}"

    assert "margin" in client.get(f"/api/datasets/{derived_id}/preview").json()["columns"]


def test_a_derived_dataset_can_be_shaped_again():
    dataset_id = upload()
    first = apply(dataset_id, [{"op": "select_columns", "columns": ["city", "revenue"]}])
    second = apply(first.json()["dataset_id"], [{"op": "limit_rows", "count": 5}])

    assert second.status_code == 200
    assert second.json()["rows"] == 5
    assert second.json()["filename"] == "orders.csv (2 steps)"


def test_applying_leaves_the_dataset_it_came_from_alone():
    dataset_id = upload()
    before = client.get(f"/api/datasets/{dataset_id}/profile").json()

    apply(dataset_id, [{"op": "limit_rows", "count": 3}])

    assert client.get(f"/api/datasets/{dataset_id}/profile").json() == before


def test_lineage_names_every_dataset_back_to_the_file():
    dataset_id = upload()
    first = apply(dataset_id, [{"op": "select_columns", "columns": ["city", "revenue"]}])
    second = apply(first.json()["dataset_id"], [{"op": "limit_rows", "count": 5}])

    chain = client.get(f"/api/datasets/{second.json()['dataset_id']}/lineage").json()["chain"]

    assert [entry["filename"] for entry in chain] == [
        "orders.csv",
        "orders.csv (1 step)",
        "orders.csv (2 steps)",
    ]
    assert chain[0]["recipe"] is None
    assert chain[1]["recipe"]["steps"][0]["op"] == "select_columns"
    assert chain[0]["rows"] == 40


def test_applying_a_refused_recipe_says_which_step_and_why():
    dataset_id = upload()
    response = apply(dataset_id, [{"op": "sort_rows", "columns": ["margin"]}])

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["step_index"] == 0
    assert detail["op"] == "sort_rows"
    assert "margin" in detail["reason"]


def test_a_recipe_that_changes_nothing_or_leaves_nothing_is_refused():
    dataset_id = upload()

    empty = apply(dataset_id, [])
    assert empty.status_code == 400
    assert "changes nothing" in empty.json()["detail"]

    nothing_left = apply(
        dataset_id,
        [
            {
                "op": "filter_rows",
                "clauses": [{"column": "revenue", "operator": "gt", "value": 1e9}],
            }
        ],
    )
    assert nothing_left.status_code == 400
    assert "leaves no rows" in nothing_left.json()["detail"]


def test_a_step_the_data_refuses_is_reported_like_any_other():
    dataset_id = upload(GAPPED, "gapped.csv")
    body = preview(
        dataset_id,
        [{"op": "fill_missing", "column": "city", "method": "median"}],
    )

    assert body["refusal"]["column"] == "city"
    assert "has no median" in body["refusal"]["reason"]


def test_a_recipe_against_a_dataset_that_is_not_there_is_a_404():
    assert client.post("/api/datasets/nope/recipe/preview", json={"steps": []}).status_code == 404
    assert client.post("/api/datasets/nope/recipe/apply", json={"steps": []}).status_code == 404
    assert client.get("/api/datasets/nope/lineage").status_code == 404


def test_a_step_that_is_not_in_the_vocabulary_is_rejected_before_anything_runs():
    dataset_id = upload()
    response = client.post(
        f"/api/datasets/{dataset_id}/recipe/preview",
        json={"steps": [{"op": "run_python", "code": "print(1)"}]},
    )

    assert response.status_code == 422
