(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena % clear

(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena % tree
.
├── arc_backend_contract_audit.md
├── arc_backend_sweep.txt
├── arena
│   ├── __init__.py
│   ├── __pycache__
│   │   └── __init__.cpython-314.pyc
│   ├── algorithms
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── arc_baseline.cpython-314.pyc
│   │   └── arc_baseline.py
│   ├── datasets
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── importer.cpython-314.pyc
│   │   ├── fixtures
│   │   ├── importer.py
│   │   ├── raw_Datas
│   │   │   ├── capacities.csv
│   │   │   ├── items.csv
│   │   │   ├── manifest.json
│   │   │   ├── README.md
│   │   │   └── scenarios.csv
│   │   └── snapshots
│   ├── evaluation
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── invariants.cpython-314.pyc
│   │   │   └── lifecycle.cpython-314.pyc
│   │   ├── invariants.py
│   │   └── lifecycle.py
│   ├── experiments
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── run_baseline.cpython-314.pyc
│   │   │   ├── run_invariant_gauntlet.cpython-314.pyc
│   │   │   ├── run_lifecycle_gauntlet.cpython-314.pyc
│   │   │   ├── run_state_machine_torture.cpython-314.pyc
│   │   │   └── run_transition_matrix.cpython-314.pyc
│   │   ├── run_baseline.py
│   │   ├── run_invariant_gauntlet.py
│   │   ├── run_lifecycle_gauntlet.py
│   │   ├── run_state_machine_torture.py
│   │   └── run_transition_matrix.py
│   └── reports
├── backend
│   ├── __pycache__
│   │   ├── conftest.cpython-312-pytest-8.3.3.pyc
│   │   └── conftest.cpython-314-pytest-9.1.1.pyc
│   ├── accounts
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── admin.cpython-314.pyc
│   │   │   ├── apps.cpython-314.pyc
│   │   │   ├── authentication.cpython-314.pyc
│   │   │   ├── models.cpython-314.pyc
│   │   │   ├── serializers.cpython-314.pyc
│   │   │   ├── tokens.cpython-314.pyc
│   │   │   ├── totp.cpython-314.pyc
│   │   │   ├── urls.cpython-314.pyc
│   │   │   └── views.cpython-314.pyc
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── authentication.py
│   │   ├── migrations
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   └── 0001_initial.cpython-314.pyc
│   │   │   └── 0001_initial.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── tests
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   │   └── test_auth.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── conftest.py
│   │   │   └── test_auth.py
│   │   ├── tokens.py
│   │   ├── totp.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── analytics
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── admin.cpython-314.pyc
│   │   │   ├── apps.cpython-314.pyc
│   │   │   ├── models.cpython-314.pyc
│   │   │   ├── serializers.cpython-314.pyc
│   │   │   ├── urls.cpython-314.pyc
│   │   │   └── views.cpython-314.pyc
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── migrations
│   │   │   ├── __init__.py
│   │   │   └── __pycache__
│   │   │       └── __init__.cpython-314.pyc
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── tests
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   └── test_api.cpython-314-pytest-9.1.1.pyc
│   │   │   └── test_api.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── arc_backend
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── settings.cpython-314.pyc
│   │   │   └── urls.cpython-314.pyc
│   │   ├── asgi.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── arena.sqlite3
│   ├── canvas_integration
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── admin.cpython-314.pyc
│   │   │   ├── apps.cpython-314.pyc
│   │   │   ├── client.cpython-314.pyc
│   │   │   ├── models.cpython-314.pyc
│   │   │   ├── serializers.cpython-314.pyc
│   │   │   ├── sync.cpython-314.pyc
│   │   │   ├── urls.cpython-314.pyc
│   │   │   └── views.cpython-314.pyc
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── client.py
│   │   ├── migrations
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   └── 0001_initial.cpython-314.pyc
│   │   │   └── 0001_initial.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── sync.py
│   │   ├── tests
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   └── test_api.cpython-314-pytest-9.1.1.pyc
│   │   │   └── test_api.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── conftest.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── admin.cpython-314.pyc
│   │   │   ├── apps.cpython-314.pyc
│   │   │   ├── exceptions.cpython-314.pyc
│   │   │   ├── fields.cpython-314.pyc
│   │   │   ├── mixins.cpython-314.pyc
│   │   │   ├── models.cpython-314.pyc
│   │   │   ├── pagination.cpython-314.pyc
│   │   │   ├── permissions.cpython-314.pyc
│   │   │   ├── schema.cpython-314.pyc
│   │   │   └── serializers.cpython-314.pyc
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── exceptions.py
│   │   ├── fields.py
│   │   ├── management
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   └── __init__.cpython-314.pyc
│   │   │   └── commands
│   │   │       ├── __init__.py
│   │   │       └── seed_demo.py
│   │   ├── migrations
│   │   │   ├── __init__.py
│   │   │   └── __pycache__
│   │   │       └── __init__.cpython-314.pyc
│   │   ├── mixins.py
│   │   ├── models.py
│   │   ├── pagination.py
│   │   ├── permissions.py
│   │   ├── schema.py
│   │   ├── serializers.py
│   │   ├── tests.py
│   │   └── views.py
│   ├── manage.py
│   ├── planning
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── admin.cpython-314.pyc
│   │   │   ├── apps.cpython-314.pyc
│   │   │   ├── models.cpython-314.pyc
│   │   │   ├── queries.cpython-314.pyc
│   │   │   ├── serializers.cpython-314.pyc
│   │   │   ├── urls.cpython-314.pyc
│   │   │   └── views.cpython-314.pyc
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── migrations
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── 0001_initial.cpython-314.pyc
│   │   │   │   ├── 0002_planninghistoryentry.cpython-314.pyc
│   │   │   │   ├── 0003_planningitem_is_deleted.cpython-314.pyc
│   │   │   │   ├── 0004_planningitem_priority_restore_context_and_more.cpython-314.pyc
│   │   │   │   ├── 0005_scheduling_state.cpython-314.pyc
│   │   │   │   └── 0006_planningitem_manual_requested_date.cpython-314.pyc
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_planninghistoryentry.py
│   │   │   ├── 0003_planningitem_is_deleted.py
│   │   │   ├── 0004_planningitem_priority_restore_context_and_more.py
│   │   │   └── 0005_scheduling_state.py
│   │   ├── models.py
│   │   ├── queries.py
│   │   ├── serializers.py
│   │   ├── services
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── hierarchy.cpython-314.pyc
│   │   │   │   ├── history.cpython-314.pyc
│   │   │   │   ├── leaf_order_sync.cpython-314.pyc
│   │   │   │   ├── overdue.cpython-314.pyc
│   │   │   │   ├── priority.cpython-314.pyc
│   │   │   │   └── scheduling.cpython-314.pyc
│   │   │   ├── hierarchy.py
│   │   │   ├── history.py
│   │   │   ├── leaf_order_sync.py
│   │   │   ├── overdue.py
│   │   │   ├── priority.py
│   │   │   └── scheduling.py
│   │   ├── tests
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_api.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_hierarchy.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_history.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_independent_ordering.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_leaf_order_sync.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_overdue.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_priority_restoration.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_priority.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_scheduling_lifecycle.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_scheduling.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_state_semantics.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_tenant_isolation.cpython-314-pytest-9.1.1.pyc
│   │   │   │   └── test_timeline_scheduling.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── conftest.py
│   │   │   ├── contract
│   │   │   │   ├── __init__.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   │   │   ├── contract_manifest.cpython-314.pyc
│   │   │   │   │   ├── test_00_contract_coverage.cpython-314-pytest-9.1.1.pyc
│   │   │   │   │   ├── test_01_canonical_state.cpython-314-pytest-9.1.1.pyc
│   │   │   │   │   ├── test_02_invariants.cpython-314-pytest-9.1.1.pyc
│   │   │   │   │   ├── test_03_creation.cpython-314-pytest-9.1.1.pyc
│   │   │   │   │   └── test_04_completion_reopen.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── conftest.py
│   │   │   │   ├── contract_manifest.py
│   │   │   │   ├── test_00_contract_coverage.py
│   │   │   │   ├── test_01_canonical_state.py
│   │   │   │   ├── test_02_invariants.py
│   │   │   │   ├── test_03_creation.py
│   │   │   │   ├── test_04_completion_reopen.py
│   │   │   │   ├── test_05_structural_frontier.py
│   │   │   │   ├── test_06_reparenting.py
│   │   │   │   ├── test_07_delete_restore_undo.py
│   │   │   │   ├── test_08_priority.py
│   │   │   │   ├── test_09_dependencies.py
│   │   │   │   ├── test_10_temporal.py
│   │   │   │   ├── test_11_anchors.py
│   │   │   │   ├── test_12_duration_progress.py
│   │   │   │   ├── test_13_large_allocations.py
│   │   │   │   ├── test_14_focus.py
│   │   │   │   ├── test_15_scheduler_timeline.py
│   │   │   │   └── test_16_transactions.py
│   │   │   ├── test_api.py
│   │   │   ├── test_hierarchy.py
│   │   │   ├── test_history.py
│   │   │   ├── test_independent_ordering.py
│   │   │   ├── test_leaf_order_sync.py
│   │   │   ├── test_overdue.py
│   │   │   ├── test_priority_restoration.py
│   │   │   ├── test_priority.py
│   │   │   ├── test_scheduling_lifecycle.py
│   │   │   ├── test_scheduling.py
│   │   │   ├── test_state_semantics.py
│   │   │   ├── test_tenant_isolation.py
│   │   │   └── test_timeline_scheduling.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── pytest.ini
│   ├── requirements-lock.txt
│   └── requirements.txt
├── backend_structure_validation.md
├── docs
│   ├── about.md
│   ├── Arc
│   │   ├── algorithm_manages.md
│   │   ├── arc_guaranteed.md
│   │   ├── canonical_state.md
│   │   ├── conflict_resolution.md
│   │   ├── domain_commands.md
│   │   ├── general_rules.md
│   │   ├── invariants.md
│   │   ├── state_transitions.md
│   │   ├── states.md
│   │   └── what_each_of_these_files_contain.md
│   ├── ARC_Scheduling_Laboratory_Design_Spec.md
│   ├── scheduling_domain_contract.md
│   └── user-intent-matrix.md
├── image.png
└── tests.zip

56 directories, 278 files
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena % cd backend
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % ls
__pycache__		canvas_integration	pytest.ini
accounts		conftest.py		requirements-lock.txt
analytics		core			requirements.txt
arc_backend		manage.py
arena.sqlite3		planning
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % ls planning/tests/contract
__init__.py				test_09_dependencies.py
__pycache__				test_10_temporal.py
conftest.py				test_11_anchors.py
contract_manifest.py			test_12_duration_progress.py
test_00_contract_coverage.py		test_13_large_allocations.py
test_01_canonical_state.py		test_14_focus.py
test_02_invariants.py			test_15_scheduler_timeline.py
test_03_creation.py			test_16_transactions.py
test_04_completion_reopen.py		test_17_view_coherence.py
test_05_structural_frontier.py		test_18_scheduler_authority.py
test_06_reparenting.py			test_19_round_trip.py
test_07_delete_restore_undo.py		test_20_state_machine_torture.py
test_08_priority.py
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % cd backend
pytest planning/tests/contract -v
cd: no such file or directory: backend
ImportError while loading conftest '/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend/conftest.py'.
conftest.py:4: in <module>
    from django.core.cache import cache
E   ModuleNotFoundError: No module named 'django'
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % pytest planning/tests/contract -v
ImportError while loading conftest '/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend/conftest.py'.
conftest.py:4: in <module>
    from django.core.cache import cache
E   ModuleNotFoundError: No module named 'django'
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m pip install -r requirements.txt
Requirement already satisfied: Django==6.1.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 4)) (6.1.1)
Requirement already satisfied: djangorestframework==3.18.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 5)) (3.18.0)
Requirement already satisfied: django-cors-headers==4.9.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 6)) (4.9.0)
Requirement already satisfied: psycopg2-binary==2.9.12 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 7)) (2.9.12)
Requirement already satisfied: django-environ==0.14.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 10)) (0.14.0)
Requirement already satisfied: cryptography==50.0.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 13)) (50.0.1)
Requirement already satisfied: djangorestframework-simplejwt==5.5.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 16)) (5.5.1)
Requirement already satisfied: pyotp==2.10.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 17)) (2.10.0)
Requirement already satisfied: qrcode==8.2 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from qrcode[pil]==8.2->-r requirements.txt (line 18)) (8.2)
Requirement already satisfied: drf-spectacular==0.30.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 21)) (0.30.0)
Requirement already satisfied: requests==2.34.2 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 24)) (2.34.2)
Requirement already satisfied: pytest==9.1.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 27)) (9.1.1)
Requirement already satisfied: pytest-django==4.14.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 28)) (4.14.0)
Requirement already satisfied: freezegun==1.5.5 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 29)) (1.5.5)
Requirement already satisfied: responses==0.26.3 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from -r requirements.txt (line 30)) (0.26.3)
Requirement already satisfied: asgiref>=3.9.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from Django==6.1.1->-r requirements.txt (line 4)) (3.12.1)
Requirement already satisfied: sqlparse>=0.5.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from Django==6.1.1->-r requirements.txt (line 4)) (0.6.0)
Requirement already satisfied: cffi>=2.0.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from cryptography==50.0.1->-r requirements.txt (line 13)) (2.1.1)
Requirement already satisfied: pyjwt>=1.7.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from djangorestframework-simplejwt==5.5.1->-r requirements.txt (line 16)) (2.14.0)
Requirement already satisfied: uritemplate>=2.0.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from drf-spectacular==0.30.0->-r requirements.txt (line 21)) (4.2.0)
Requirement already satisfied: PyYAML>=5.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from drf-spectacular==0.30.0->-r requirements.txt (line 21)) (6.0.3)
Requirement already satisfied: jsonschema>=2.6.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from drf-spectacular==0.30.0->-r requirements.txt (line 21)) (4.26.0)
Requirement already satisfied: inflection>=0.3.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from drf-spectacular==0.30.0->-r requirements.txt (line 21)) (0.5.1)
Requirement already satisfied: charset_normalizer<4,>=2 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from requests==2.34.2->-r requirements.txt (line 24)) (3.5.1)
Requirement already satisfied: idna<4,>=2.5 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from requests==2.34.2->-r requirements.txt (line 24)) (3.19)
Requirement already satisfied: urllib3<3,>=1.26 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from requests==2.34.2->-r requirements.txt (line 24)) (2.8.0)
Requirement already satisfied: certifi>=2023.5.7 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from requests==2.34.2->-r requirements.txt (line 24)) (2026.7.22)
Requirement already satisfied: iniconfig>=1.0.1 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from pytest==9.1.1->-r requirements.txt (line 27)) (2.3.0)
Requirement already satisfied: packaging>=22 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from pytest==9.1.1->-r requirements.txt (line 27)) (26.3)
Requirement already satisfied: pluggy<2,>=1.5 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from pytest==9.1.1->-r requirements.txt (line 27)) (1.6.0)
Requirement already satisfied: pygments>=2.7.2 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from pytest==9.1.1->-r requirements.txt (line 27)) (2.21.0)
Requirement already satisfied: python-dateutil>=2.7 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from freezegun==1.5.5->-r requirements.txt (line 29)) (2.9.0.post0)
Requirement already satisfied: pillow>=9.1.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from qrcode[pil]==8.2->-r requirements.txt (line 18)) (12.3.0)
Requirement already satisfied: pycparser in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from cffi>=2.0.0->cryptography==50.0.1->-r requirements.txt (line 13)) (3.0)
Requirement already satisfied: attrs>=22.2.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from jsonschema>=2.6.0->drf-spectacular==0.30.0->-r requirements.txt (line 21)) (26.1.0)
Requirement already satisfied: jsonschema-specifications>=2023.03.6 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from jsonschema>=2.6.0->drf-spectacular==0.30.0->-r requirements.txt (line 21)) (2025.9.1)
Requirement already satisfied: referencing>=0.28.4 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from jsonschema>=2.6.0->drf-spectacular==0.30.0->-r requirements.txt (line 21)) (0.37.0)
Requirement already satisfied: rpds-py>=0.25.0 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from jsonschema>=2.6.0->drf-spectacular==0.30.0->-r requirements.txt (line 21)) (2026.6.3)
Requirement already satisfied: six>=1.5 in /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages (from python-dateutil>=2.7->freezegun==1.5.5->-r requirements.txt (line 29)) (1.17.0)
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -c "import django; print(django.get_version())"
6.1.1
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % pytest planning/tests/contract -v
ImportError while loading conftest '/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend/conftest.py'.
conftest.py:4: in <module>
    from django.core.cache import cache
E   ModuleNotFoundError: No module named 'django'
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -c "import django; print(django.get_version())"
6.1.1
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % pytest planning/tests/contract -v
ImportError while loading conftest '/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend/conftest.py'.
conftest.py:4: in <module>
    from django.core.cache import cache
E   ModuleNotFoundError: No module named 'django'
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % which python
which pytest

python -c "import sys; print(sys.executable)"
pytest --version

python -m pytest planning/tests/contract -v
/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/bin/python
/Library/Frameworks/Python.framework/Versions/3.12/bin/pytest
/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/bin/python
pytest 8.3.3
=================================== test session starts ===================================
platform darwin -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0
django: version: 6.1.1, settings: arc_backend.settings (from ini)
rootdir: /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend
configfile: pytest.ini
plugins: django-4.14.0
collected 185 items                                                                       

planning/tests/contract/test_01_canonical_state.py .F......FFF...                   [  7%]
planning/tests/contract/test_02_invariants.py ..........                            [ 12%]
planning/tests/contract/test_03_creation.py .F..FFF                                 [ 16%]
planning/tests/contract/test_04_completion_reopen.py F...FFFFF..                    [ 22%]
planning/tests/contract/test_05_structural_frontier.py ......FF                     [ 27%]
planning/tests/contract/test_06_reparenting.py .....F                               [ 30%]
planning/tests/contract/test_07_delete_restore_undo.py .FFFFFF...                   [ 35%]
planning/tests/contract/test_08_priority.py .........                               [ 40%]
planning/tests/contract/test_09_dependencies.py FFFFFFFFFF                          [ 45%]
planning/tests/contract/test_10_temporal.py ..........                              [ 51%]
planning/tests/contract/test_11_anchors.py FFFFFFFFFFF                              [ 57%]
planning/tests/contract/test_12_duration_progress.py F...FFFFFFF..FFFF              [ 66%]
planning/tests/contract/test_13_large_allocations.py FFFFFFFF                       [ 70%]
planning/tests/contract/test_14_focus.py FFFFFFFFF                                  [ 75%]
planning/tests/contract/test_15_scheduler_timeline.py .........                     [ 80%]
planning/tests/contract/test_17_view_coherence.py .FFFFF                            [ 83%]
planning/tests/contract/test_18_scheduler_authority.py FFF....                      [ 87%]
planning/tests/contract/test_19_round_trip.py F..F.                                 [ 90%]
planning/tests/contract/test_16_transactions.py FF.FF...                            [ 94%]
planning/tests/contract/test_20_state_machine_torture.py .....                      [ 97%]
planning/tests/contract/test_00_contract_coverage.py ...FF                          [100%]

======================================== FAILURES =========================================
_ test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] _
planning/tests/contract/test_01_canonical_state.py:61: in test_required_existing_canonical_state_is_persisted
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' state. Expected one of ('manual_requested_date',); PlanningItem has {'children', 'canvas_object_id', 'canvas_object_type', 'description', 'assignment_detail', 'parent', 'schedule_is_manual', 'tags', 'start_date', 'scheduled_date', 'duration_category', 'priority_position', 'due_date', 'sibling_order', 'is_deleted', 'planningitemtag', 'user', 'priority_restore_context', 'item_type', 'title', 'updated_at', 'is_completed', 'id', 'created_at'}
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('manual_requested_date',))
___ test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] ___
planning/tests/contract/test_01_canonical_state.py:69: in test_required_new_canonical_state_exists
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expected one of ('percent_completed', 'completion_percent', 'progress_percent'). This is canonical user/domain state, not a scheduler-only value.
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('percent_completed', 'completion_percent', 'progress_percent'))
___________________ test_scheduled_date_and_anchor_are_distinct_fields ____________________
planning/tests/contract/test_01_canonical_state.py:79: in test_scheduled_date_and_anchor_are_distinct_fields
    assert "manual_requested_date" in names
E   AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________________ test_scheduler_date_can_change_without_destroying_anchor _________________
planning/tests/contract/test_01_canonical_state.py:89: in test_scheduler_date_can_change_without_destroying_anchor
    pytest.fail("MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent")
E   Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
____________ test_C2_child_creation_defaults_release_and_deadline_from_parent _____________
planning/tests/contract/test_03_creation.py:76: in test_C2_child_creation_defaults_release_and_deadline_from_parent
    assert child.start_date == parent.start_date, (
E   AssertionError: C2 MISSING: child creation must default release/start_date from parent
E   assert None == datetime.date(2026, 9, 22)
E    +  where None = <PlanningItem: [TASK] Child>.start_date
E    +  and   datetime.date(2026, 9, 22) = <PlanningItem: [TASK] Parent>.start_date
___ test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it ___
planning/tests/contract/test_03_creation.py:144: in test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it
    pytest.fail("C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor")
E   Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
____ test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion ____
planning/tests/contract/test_03_creation.py:180: in test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion
    assert parent.is_completed is False, (
E   AssertionError: C5 MISSING: a completed parent cannot remain semantically completed after an unfinished required child is added
E   assert True is False
E    +  where True = <PlanningItem: [TASK] Completed parent>.is_completed
______ test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress ______
planning/tests/contract/test_03_creation.py:192: in test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress
    pytest.fail(
E   Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable tasks
__________________ test_CR1_complete_atomic_leaf_leaves_active_frontier ___________________
planning/tests/contract/test_04_completion_reopen.py:49: in test_CR1_complete_atomic_leaf_leaves_active_frontier
    assert item.priority_position is not None
E   assert None is not None
E    +  where None = <PlanningItem: [TASK] Atomic>.priority_position
_____________ test_CR3_CR6_splittable_completion_has_canonical_progress_state _____________
planning/tests/contract/test_04_completion_reopen.py:123: in test_CR3_CR6_splittable_completion_has_canonical_progress_state
    assert field is not None, (
E   AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible completed progress-segment history for splittable tasks
E   assert None is not None
__________ test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed ___________
planning/tests/contract/test_04_completion_reopen.py:136: in test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed
    assert progress is not None, (
E   AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____________ test_CR4_reopening_one_progress_segment_requires_segment_identity ____________
planning/tests/contract/test_04_completion_reopen.py:155: in test_CR4_reopening_one_progress_segment_requires_segment_identity
    assert progress is not None, (
E   AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____ test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution ____
planning/tests/contract/test_04_completion_reopen.py:175: in test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it exists, completing B while prerequisite A is incomplete must require cancel OR explicit edge removal; ARC may not silently break A->B.
E   assert None is not None
_________ test_CR8_reopening_completed_prerequisite_requires_explicit_resolution __________
planning/tests/contract/test_04_completion_reopen.py:184: in test_CR8_reopening_completed_prerequisite_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopening prerequisite A while dependent B remains complete must require explicit conflict resolution rather than silently violating/removing A->B.
E   assert None is not None
__ test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child ___
planning/tests/contract/test_05_structural_frontier.py:146: in test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child
    assert field is not None, (
E   AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must exist before anchor suspension/inheritance can be implemented
E   assert None is not None
_________ test_H7_reversing_anchored_structural_transition_restores_parent_intent _________
planning/tests/contract/test_05_structural_frontier.py:174: in test_H7_reversing_anchored_structural_transition_restores_parent_intent
    assert field is not None, (
E   AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
E   assert None is not None
_______ test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent ________
planning/tests/contract/test_06_reparenting.py:146: in test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent
    assert dependency is not None, (
E   AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once present, reparenting an endpoint must preserve valid edges and reject/require explicit resolution for invalid semantics; it may never silently delete the dependency.
E   assert None is not None
_________________ test_D2_subtree_delete_requires_atomic_domain_semantics _________________
planning/tests/contract/test_07_delete_restore_undo.py:85: in test_D2_subtree_delete_requires_atomic_domain_semantics
    assert delete is not None, (
E   AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/subtree so active descendants/parent references cannot be left dangling by a partial multi-write operation
E   assert None is not None
___________ test_D3_deleting_dependency_endpoint_requires_edge_restore_history ____________
planning/tests/contract/test_07_delete_restore_undo.py:94: in test_D3_deleting_dependency_endpoint_requires_edge_restore_history
    assert dependency is not None, (
E   AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting an endpoint must suspend/remove incident active edges while retaining enough canonical/history context for safe restore.
E   assert None is not None
_____________ test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip _____________
planning/tests/contract/test_07_delete_restore_undo.py:103: in test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip
    assert restore is not None, (
E   AssertionError: D4 MISSING: restore must be a domain command that validates the original parent/dependency relationships against the current world; raw is_deleted=False is insufficient.
E   assert None is not None
_____________________ test_D5_restore_must_revalidate_hierarchy_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:112: in test_D5_restore_must_revalidate_hierarchy_cycle
    assert restore is not None, (
E   AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore must reject/redirect an original parent relationship that would now create a hierarchy cycle.
E   assert None is not None
____________________ test_D6_restore_must_revalidate_dependency_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:122: in test_D6_restore_must_revalidate_dependency_cycle
    assert restore is not None and dependency is not None, (
E   AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required. An old dependency edge may not be silently reactivated if it would create a dependency cycle in the present world.
E   assert (None is not None)
________ test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it _________
planning/tests/contract/test_07_delete_restore_undo.py:131: in test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it
    assert "manual_requested_date" in names, (
E   AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority ________
planning/tests/contract/test_09_dependencies.py:88: in test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_____________________ test_DP2_self_dependency_is_rejected_atomically _____________________
planning/tests/contract/test_09_dependencies.py:105: in test_DP2_self_dependency_is_rejected_atomically
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__________ test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges __________
planning/tests/contract/test_09_dependencies.py:120: in test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____________________ test_DP1_DP7_dependency_edits_are_tenant_isolated ____________________
planning/tests/contract/test_09_dependencies.py:137: in test_DP1_DP7_dependency_edits_are_tenant_isolated
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
________ test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier ________
planning/tests/contract/test_09_dependencies.py:148: in test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_________________ test_DP3_completing_prerequisite_may_unblock_dependant __________________
planning/tests/contract/test_09_dependencies.py:160: in test_DP3_completing_prerequisite_may_unblock_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
______________ test_DP4_reopening_prerequisite_reblocks_unfinished_dependant ______________
planning/tests/contract/test_09_dependencies.py:172: in test_DP4_reopening_prerequisite_reblocks_unfinished_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_ test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete _
planning/tests/contract/test_09_dependencies.py:187: in test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__ test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete __
planning/tests/contract/test_09_dependencies.py:205: in test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____ test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold _____
planning/tests/contract/test_09_dependencies.py:225: in test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold
    model, _ = _require_dependency_layer()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
______________ test_A1_valid_anchor_is_canonical_and_distinct_from_priority _______________
planning/tests/contract/test_11_anchors.py:81: in test_A1_valid_anchor_is_canonical_and_distinct_from_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
___________________ test_A2_moving_anchor_changes_canonical_anchor_date ___________________
planning/tests/contract/test_11_anchors.py:90: in test_A2_moving_anchor_changes_canonical_anchor_date
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__________ test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority ___________
planning/tests/contract/test_11_anchors.py:103: in test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change _____
planning/tests/contract/test_11_anchors.py:119: in test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change
    _set_anchor(item, due + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__ test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change ___
planning/tests/contract/test_11_anchors.py:141: in test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change
    _set_anchor(item, today + timedelta(days=1))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
______________ test_A6_passing_anchor_date_does_not_itself_make_task_overdue ______________
planning/tests/contract/test_11_anchors.py:158: in test_A6_passing_anchor_date_does_not_itself_make_task_overdue
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____ test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace _____
planning/tests/contract/test_11_anchors.py:172: in test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____________ test_A9_automatic_missed_schedule_is_not_converted_into_anchor ______________
planning/tests/contract/test_11_anchors.py:224: in test_A9_automatic_missed_schedule_is_not_converted_into_anchor
    assert getattr(item, _anchor_field()) is None
                         ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
__ test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor __
planning/tests/contract/test_11_anchors.py:231: in test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
_____________ test_A10_reversing_structural_episode_can_restore_parent_anchor _____________
planning/tests/contract/test_11_anchors.py:246: in test_A10_reversing_structural_episode_can_restore_parent_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer _____
planning/tests/contract/test_11_anchors.py:263: in test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer
    assert any(callable(getattr(service, n, None)) for n in names), (
E   AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user-created infeasible or overloaded plans
E   assert False
E    +  where False = any(<generator object test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer.<locals>.<genexpr> at 0x10ee1d040>)
______ test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories _______
planning/tests/contract/test_12_duration_progress.py:105: in test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories
    assert EXPECTED_CLASSES <= values, (
E   AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >16h as distinct mutually-exclusive semantic classes. Current values: ['MIN_20_TO_60', 'OVER_60_MIN', 'UNDER_20_MIN']
E   assert {'OVER_16_HOU...NDER_8_HOURS'} <= {'MIN_20_TO_6...UNDER_20_MIN'}
E     
E     Extra items in the left set:
E     'UNDER_20_MINUTES'
E     'UNDER_8_HOURS'
E     'OVER_16_HOURS'
E     'UNDER_1_HOUR'
E     'UNDER_16_HOURS'
E     'UNDER_4_HOURS'
______ test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] ______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_______ test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed ________
planning/tests/contract/test_12_duration_progress.py:137: in test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
____________ test_E3_splittable_to_atomic_discards_partial_progress_semantics _____________
planning/tests/contract/test_12_duration_progress.py:150: in test_E3_splittable_to_atomic_discards_partial_progress_semantics
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_________ test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress _________
planning/tests/contract/test_12_duration_progress.py:166: in test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_____________ test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress _____________
planning/tests/contract/test_12_duration_progress.py:178: in test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress
    assert _get_progress(item) in (0, 0.0, None)
           ^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:98: in _get_progress
    return getattr(item, _progress_field())
                         ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_ test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal _
planning/tests/contract/test_12_duration_progress.py:210: in test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal
    assert model is not None, (
E   AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonical progress-segment/history identity so future scheduler proposals can change without rewriting confirmed progress
E   assert None is not None
________________ test_DUR009_reversing_one_completed_segment_can_be_local _________________
planning/tests/contract/test_12_duration_progress.py:220: in test_DUR009_reversing_one_completed_segment_can_be_local
    assert model is not None and service is not None, (
E   AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress service
E   assert (None is not None)
_____ test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations _____
planning/tests/contract/test_12_duration_progress.py:241: in test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations
    assert any(callable(getattr(service, n, None)) for n in complete_names)
E   assert False
E    +  where False = any(<generator object test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations.<locals>.<genexpr> at 0x10ee1ec40>)
___________ test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children ___________
planning/tests/contract/test_12_duration_progress.py:247: in test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children
    assert model is not None, "DUR-011 MISSING PREREQUISITE: progress segment model"
E   AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
E   assert None is not None
______ test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work ______
planning/tests/contract/test_13_large_allocations.py:96: in test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work
    assert model is not None, "ALLOC-001 MISSING: allocation/progress segment model"
E   AssertionError: ALLOC-001 MISSING: allocation/progress segment model
E   assert None is not None
______ test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress ______
planning/tests/contract/test_13_large_allocations.py:109: in test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______ test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress _______
planning/tests/contract/test_13_large_allocations.py:125: in test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress
    assert model is not None and service is not None
E   assert (None is not None)
_______________ test_L4_commenced_task_only_allocates_remaining_percentage ________________
planning/tests/contract/test_13_large_allocations.py:146: in test_L4_commenced_task_only_allocates_remaining_percentage
    assert model is not None
E   assert None is not None
____________ test_L5_reopening_one_completed_segment_reduces_only_its_progress ____________
planning/tests/contract/test_13_large_allocations.py:161: in test_L5_reopening_one_completed_segment_reduces_only_its_progress
    assert model is not None and service is not None
E   assert (None is not None)
_________________ test_L6_one_hundred_percent_reconciles_task_to_complete _________________
planning/tests/contract/test_13_large_allocations.py:175: in test_L6_one_hundred_percent_reconciles_task_to_complete
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
____________ test_L7_semantic_decomposition_does_not_fabricate_child_progress _____________
planning/tests/contract/test_13_large_allocations.py:196: in test_L7_semantic_decomposition_does_not_fabricate_child_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______________ test_L8_allocation_projection_is_not_semantic_planning_item _______________
planning/tests/contract/test_13_large_allocations.py:209: in test_L8_allocation_projection_is_not_semantic_planning_item
    assert model is not None
E   assert None is not None
_________________________ test_F1_focus_projection_service_exists _________________________
planning/tests/contract/test_14_focus.py:56: in test_F1_focus_projection_service_exists
    assert service is not None, "FOC-001 MISSING: Focus projection/service"
E   AssertionError: FOC-001 MISSING: Focus projection/service
E   assert None is not None
__________ test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket __________
planning/tests/contract/test_14_focus.py:62: in test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket
    assert service is not None
E   assert None is not None
_________________ test_F2_lookahead_is_read_only_and_does_not_reschedule __________________
planning/tests/contract/test_14_focus.py:71: in test_F2_lookahead_is_read_only_and_does_not_reschedule
    assert service is not None
E   assert None is not None
_________________ test_F3_F4_selecting_current_focus_is_convenience_only __________________
planning/tests/contract/test_14_focus.py:97: in test_F3_F4_selecting_current_focus_is_convenience_only
    assert service is not None
E   assert None is not None
__________________ test_F5_do_today_translates_to_explicit_today_anchor ___________________
planning/tests/contract/test_14_focus.py:117: in test_F5_do_today_translates_to_explicit_today_anchor
    assert service is not None
E   assert None is not None
__________ test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent __________
planning/tests/contract/test_14_focus.py:136: in test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent
    assert service is not None
E   assert None is not None
____________ test_F7_explicit_focus_reprioritise_uses_global_priority_service _____________
planning/tests/contract/test_14_focus.py:155: in test_F7_explicit_focus_reprioritise_uses_global_priority_service
    assert service is not None
E   assert None is not None
___________________ test_F8_wrong_visual_bucket_cannot_mutate_duration ____________________
planning/tests/contract/test_14_focus.py:167: in test_F8_wrong_visual_bucket_cannot_mutate_duration
    assert service is not None
E   assert None is not None
________ test_F9_non_executable_current_focus_is_cleared_without_planning_mutation ________
planning/tests/contract/test_14_focus.py:177: in test_F9_non_executable_current_focus_is_cleared_without_planning_mutation
    assert service is not None
E   assert None is not None
______ test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections _______
planning/tests/contract/test_17_view_coherence.py:124: in test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections
    move(*args)
/opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:85: in inner
    return func(*args, **kwds)
           ^^^^^^^^^^^^^^^^^^^
planning/services/priority.py:225: in reorder
    raise ValidationError('That task is not in the priority order.')
E   django.core.exceptions.ValidationError: ['That task is not in the priority order.']
____________ test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop _____________
planning/tests/contract/test_17_view_coherence.py:142: in test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop
    assert "manual_requested_date" in fields, (
E   AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
____________ test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning _____________
planning/tests/contract/test_17_view_coherence.py:192: in test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning
    assert service is not None, "VIEW-003 prerequisite: Focus projection"
E   AssertionError: VIEW-003 prerequisite: Focus projection
E   assert None is not None
___________ test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts ____________
planning/tests/contract/test_17_view_coherence.py:234: in test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts
    assert service is not None
E   assert None is not None
___________ test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes ____________
planning/tests/contract/test_17_view_coherence.py:263: in test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes
    assert commands is not None, (
E   AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boundary rather than separate serializer/view databases
E   assert None is not None
___________________ test_AUTH_001_hard_anchor_survives_scheduler_rerun ____________________
planning/tests/contract/test_18_scheduler_authority.py:84: in test_AUTH_001_hard_anchor_survives_scheduler_rerun
    assert "manual_requested_date" in fields, (
E   AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
_______________ test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts _______________
planning/tests/contract/test_18_scheduler_authority.py:118: in test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts
    assert _canonical(item) == before, (
E   AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may not
E   assert {'title': 'Ca...': False, ...} == {'title': 'Ca...': False, ...}
E     
E     Omitting 8 identical items, use -vv to show
E     Differing items:
E     {'priority_position': 1} != {'priority_position': None}
E     Use -v to get more diff
____________ test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges _____________
planning/tests/contract/test_18_scheduler_authority.py:127: in test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges
    assert dependency is not None, (
E   AssertionError: AUTH-002 prerequisite: dependency graph implementation
E   assert None is not None
____________ test_RT_001_delete_restore_round_trip_preserves_semantic_identity ____________
planning/tests/contract/test_19_round_trip.py:78: in test_RT_001_delete_restore_round_trip_preserves_semantic_identity
    assert delete is not None and restore is not None, (
E   AssertionError: RT-001 prerequisite: validated delete + restore domain commands
E   assert (None is not None)
____________ test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts ____________
planning/tests/contract/test_19_round_trip.py:163: in test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts
    assert "manual_requested_date" in fields, (
E   AssertionError: RT-004 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit _________
planning/tests/contract/test_16_transactions.py:51: in test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit
    assert commands is not None, (
E   AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather than independent serializer/model writes
E   assert None is not None
_________________ test_X1_failed_multi_field_edit_rolls_back_every_field __________________
planning/tests/contract/test_16_transactions.py:63: in test_X1_failed_multi_field_edit_rolls_back_every_field
    assert commands is not None
E   assert None is not None
___________ test_X3_risky_overload_needs_confirmation_capability_before_commit ____________
planning/tests/contract/test_16_transactions.py:95: in test_X3_risky_overload_needs_confirmation_capability_before_commit
    assert commands is not None
E   assert None is not None
________ test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised _________
planning/tests/contract/test_16_transactions.py:104: in test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised
    assert commands is not None
E   assert None is not None
_____________ test_each_contract_area_is_claimed_by_its_designated_test_file ______________
planning/tests/contract/test_00_contract_coverage.py:104: in test_each_contract_area_is_claimed_by_its_designated_test_file
    assert not problems, (
E   AssertionError: Some frozen requirements have no test in their designated module: {'test_01_canonical_state.py': {'missing_contract_ids': ['CAN-001', 'CAN-002', 'CAN-003', 'CAN-004', 'CAN-005', 'CAN-006', 'CAN-007', 'CAN-008', 'CAN-009', 'CAN-010']}, 'test_02_invariants.py': {'missing_contract_ids': ['HIE-001', 'HIE-002']}, 'test_03_creation.py': {'missing_contract_ids': ['CRE-001', 'CRE-002', 'CRE-003', 'CRE-004', 'CRE-005', 'CRE-006', 'CRE-007']}, 'test_04_completion_reopen.py': {'missing_contract_ids': ['CMP-001', 'CMP-002', 'CMP-003', 'CMP-004', 'CMP-005', 'CMP-006']}, 'test_05_structural_frontier.py': {'missing_contract_ids': ['HIE-003', 'HIE-004', 'HIE-005', 'HIE-006', 'HIE-007', 'HIE-008']}, 'test_06_reparenting.py': {'missing_contract_ids': ['REP-001', 'REP-002', 'REP-003', 'REP-004', 'REP-005']}, 'test_07_delete_restore_undo.py': {'missing_contract_ids': ['DEL-001', 'DEL-002', 'DEL-003', 'DEL-004', 'DEL-005', 'DEL-006']}, 'test_08_priority.py': {'missing_contract_ids': ['PRI-001', 'PRI-002', 'PRI-003', 'PRI-004', 'PRI-005', 'PRI-006', 'PRI-007', 'PRI-008']}, 'test_09_dependencies.py': {'missing_contract_ids': ['DEP-001', 'DEP-002', 'DEP-003', 'DEP-004', 'DEP-005', 'DEP-006', 'DEP-007', 'DEP-008', 'DEP-009', 'DEP-010']}, 'test_10_temporal.py': {'missing_contract_ids': ['TMP-001', 'TMP-002', 'TMP-003', 'TMP-004', 'TMP-005', 'TMP-006', 'TMP-007', 'TMP-008', 'TMP-009', 'TMP-010', 'TMP-011']}, 'test_11_anchors.py': {'missing_contract_ids': ['ANC-001', 'ANC-002', 'ANC-003', 'ANC-004', 'ANC-005', 'ANC-006', 'ANC-007', 'ANC-008', 'ANC-009', 'ANC-010', 'ANC-011', 'ANC-012']}, 'test_12_duration_progress.py': {'missing_contract_ids': ['DUR-001', 'DUR-002', 'DUR-003', 'DUR-004', 'DUR-005', 'DUR-006', 'DUR-007', 'DUR-008', 'DUR-009', 'DUR-010', 'DUR-011']}, 'test_13_large_allocations.py': {'missing_contract_ids': ['ALL-001', 'ALL-002', 'ALL-003', 'ALL-004', 'ALL-005', 'ALL-006', 'ALL-007', 'ALL-008']}, 'test_14_focus.py': {'missing_contract_ids': ['FOC-001', 'FOC-002', 'FOC-003', 'FOC-004', 'FOC-005', 'FOC-006', 'FOC-007', 'FOC-008', 'FOC-009', 'FOC-010']}, 'test_15_scheduler_timeline.py': {'missing_contract_ids': ['SCH-001', 'SCH-002', 'SCH-003', 'SCH-004', 'SCH-005', 'SCH-006', 'SCH-007', 'SCH-008', 'SCH-009', 'SCH-010', 'SCH-011', 'SCH-012', 'SCH-013']}, 'test_16_transactions.py': {'missing_contract_ids': ['TRX-001', 'TRX-002', 'TRX-003']}, 'test_17_view_coherence.py': {'missing_contract_ids': ['VIEW-001', 'VIEW-002', 'VIEW-003']}, 'test_18_scheduler_authority.py': {'missing_contract_ids': ['AUTH-001', 'AUTH-002', 'AUTH-003', 'AUTH-004']}, 'test_19_round_trip.py': {'missing_contract_ids': ['RT-001', 'RT-002', 'RT-003', 'RT-004', 'RT-005', 'RT-006']}, 'test_20_state_machine_torture.py': {'missing_contract_ids': ['RT-001', 'RT-002', 'RT-003', 'RT-004', 'RT-005', 'RT-006']}}
E   assert not {'test_01_canonical_state.py': {'missing_contract_ids': ['CAN-001', 'CAN-002', 'CAN-003', 'CAN-004', 'CAN-005', 'CAN-0...mpletion_reopen.py': {'missing_contract_ids': ['CMP-001', 'CMP-002', 'CMP-003', 'CMP-004', 'CMP-005', 'CMP-006']}, ...}
___________________ test_every_frozen_requirement_is_covered_somewhere ____________________
planning/tests/contract/test_00_contract_coverage.py:113: in test_every_frozen_requirement_is_covered_somewhere
    assert not missing, (
E   AssertionError: Contract requirements without executable tests: ALL-001, ALL-002, ALL-003, ALL-004, ALL-005, ALL-006, ALL-007, ALL-008, ANC-001, ANC-002, ANC-003, ANC-004, ANC-005, ANC-006, ANC-007, ANC-008, ANC-009, ANC-010, ANC-011, ANC-012, AUTH-001, AUTH-002, AUTH-003, AUTH-004, CAN-001, CAN-002, CAN-003, CAN-004, CAN-005, CAN-006, CAN-007, CAN-008, CAN-009, CAN-010, CMP-001, CMP-002, CMP-003, CMP-004, CMP-005, CMP-006, CRE-001, CRE-002, CRE-003, CRE-004, CRE-005, CRE-006, CRE-007, DEL-001, DEL-002, DEL-003, DEL-004, DEL-005, DEL-006, DEP-001, DEP-002, DEP-003, DEP-004, DEP-005, DEP-006, DEP-007, DEP-008, DEP-009, DEP-010, DUR-001, DUR-002, DUR-003, DUR-004, DUR-005, DUR-006, DUR-007, DUR-008, DUR-009, DUR-010, DUR-011, FOC-001, FOC-002, FOC-003, FOC-004, FOC-005, FOC-006, FOC-007, FOC-008, FOC-009, FOC-010, HIE-001, HIE-002, HIE-003, HIE-004, HIE-005, HIE-006, HIE-007, HIE-008, PRI-001, PRI-002, PRI-003, PRI-004, PRI-005, PRI-006, PRI-007, PRI-008, REP-001, REP-002, REP-003, REP-004, REP-005, RT-001, RT-002, RT-003, RT-004, RT-005, RT-006, SCH-001, SCH-002, SCH-003, SCH-004, SCH-005, SCH-006, SCH-007, SCH-008, SCH-009, SCH-010, SCH-011, SCH-012, SCH-013, TMP-001, TMP-002, TMP-003, TMP-004, TMP-005, TMP-006, TMP-007, TMP-008, TMP-009, TMP-010, TMP-011, TRX-001, TRX-002, TRX-003, VIEW-001, VIEW-002, VIEW-003
E   assert not ['ALL-001', 'ALL-002', 'ALL-003', 'ALL-004', 'ALL-005', 'ALL-006', ...]
================================= short test summary info =================================
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] - AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' s...
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] - AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expect...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduled_date_and_anchor_are_distinct_fields - AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduler_date_can_change_without_destroying_anchor - Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
FAILED planning/tests/contract/test_03_creation.py::test_C2_child_creation_defaults_release_and_deadline_from_parent - AssertionError: C2 MISSING: child creation must default release/start_date from parent
FAILED planning/tests/contract/test_03_creation.py::test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it - Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_03_creation.py::test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion - AssertionError: C5 MISSING: a completed parent cannot remain semantically completed af...
FAILED planning/tests/contract/test_03_creation.py::test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress - Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable t...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR1_complete_atomic_leaf_leaves_active_frontier - assert None is not None
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_CR6_splittable_completion_has_canonical_progress_state - AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible comple...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed - AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR4_reopening_one_progress_segment_requires_segment_identity - AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution - AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR8_reopening_completed_prerequisite_requires_explicit_resolution - AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopeni...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child - AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must e...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H7_reversing_anchored_structural_transition_restores_parent_intent - AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_06_reparenting.py::test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent - AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once pr...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D2_subtree_delete_requires_atomic_domain_semantics - AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D3_deleting_dependency_endpoint_requires_edge_restore_history - AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip - AssertionError: D4 MISSING: restore must be a domain command that validates the origin...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D5_restore_must_revalidate_hierarchy_cycle - AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore ...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D6_restore_must_revalidate_dependency_cycle - AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required....
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it - AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP2_self_dependency_is_rejected_atomically - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_DP7_dependency_edits_are_tenant_isolated - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP3_completing_prerequisite_may_unblock_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_reopening_prerequisite_reblocks_unfinished_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_11_anchors.py::test_A1_valid_anchor_is_canonical_and_distinct_from_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A2_moving_anchor_changes_canonical_anchor_date - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A6_passing_anchor_date_does_not_itself_make_task_overdue - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_automatic_missed_schedule_is_not_converted_into_anchor - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A10_reversing_structural_episode_can_restore_parent_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer - AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories - AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E3_splittable_to_atomic_discards_partial_progress_semantics - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal - AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonic...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR009_reversing_one_completed_segment_can_be_local - AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress ser...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations - assert False
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children - AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work - AssertionError: ALLOC-001 MISSING: allocation/progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L4_commenced_task_only_allocates_remaining_percentage - assert None is not None
FAILED planning/tests/contract/test_13_large_allocations.py::test_L5_reopening_one_completed_segment_reduces_only_its_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L6_one_hundred_percent_reconciles_task_to_complete - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L7_semantic_decomposition_does_not_fabricate_child_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L8_allocation_projection_is_not_semantic_planning_item - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_projection_service_exists - AssertionError: FOC-001 MISSING: Focus projection/service
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F2_lookahead_is_read_only_and_does_not_reschedule - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F3_F4_selecting_current_focus_is_convenience_only - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F5_do_today_translates_to_explicit_today_anchor - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F7_explicit_focus_reprioritise_uses_global_priority_service - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F8_wrong_visual_bucket_cannot_mutate_duration - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F9_non_executable_current_focus_is_cleared_without_planning_mutation - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections - django.core.exceptions.ValidationError: ['That task is not in the priority order.']
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop - AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning - AssertionError: VIEW-003 prerequisite: Focus projection
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes - AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boun...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_001_hard_anchor_survives_scheduler_rerun - AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts - AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges - AssertionError: AUTH-002 prerequisite: dependency graph implementation
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_001_delete_restore_round_trip_preserves_semantic_identity - AssertionError: RT-001 prerequisite: validated delete + restore domain commands
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts - AssertionError: RT-004 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_16_transactions.py::test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit - AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather ...
FAILED planning/tests/contract/test_16_transactions.py::test_X1_failed_multi_field_edit_rolls_back_every_field - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X3_risky_overload_needs_confirmation_capability_before_commit - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised - assert None is not None
FAILED planning/tests/contract/test_00_contract_coverage.py::test_each_contract_area_is_claimed_by_its_designated_test_file - AssertionError: Some frozen requirements have no test in their designated module: {'te...
FAILED planning/tests/contract/test_00_contract_coverage.py::test_every_frozen_requirement_is_covered_somewhere - AssertionError: Contract requirements without executable tests: ALL-001, ALL-002, ALL-...
============================= 89 failed, 96 passed in 41.84s ==============================
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m pytest planning/tests/contract -v
=================================== test session starts ===================================
platform darwin -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0
django: version: 6.1.1, settings: arc_backend.settings (from ini)
rootdir: /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend
configfile: pytest.ini
plugins: django-4.14.0
collected 185 items                                                                       

planning/tests/contract/test_01_canonical_state.py .F......FFF...                   [  7%]
planning/tests/contract/test_02_invariants.py ..........                            [ 12%]
planning/tests/contract/test_03_creation.py .F..FFF                                 [ 16%]
planning/tests/contract/test_04_completion_reopen.py F...FFFFF..                    [ 22%]
planning/tests/contract/test_05_structural_frontier.py ......FF                     [ 27%]
planning/tests/contract/test_06_reparenting.py .....F                               [ 30%]
planning/tests/contract/test_07_delete_restore_undo.py .FFFFFF...                   [ 35%]
planning/tests/contract/test_08_priority.py .........                               [ 40%]
planning/tests/contract/test_09_dependencies.py FFFFFFFFFF                          [ 45%]
planning/tests/contract/test_10_temporal.py ..........                              [ 51%]
planning/tests/contract/test_11_anchors.py FFFFFFFFFFF                              [ 57%]
planning/tests/contract/test_12_duration_progress.py F...FFFFFFF..FFFF              [ 66%]
planning/tests/contract/test_13_large_allocations.py FFFFFFFF                       [ 70%]
planning/tests/contract/test_14_focus.py FFFFFFFFF                                  [ 75%]
planning/tests/contract/test_15_scheduler_timeline.py .........                     [ 80%]
planning/tests/contract/test_17_view_coherence.py .FFFFF                            [ 83%]
planning/tests/contract/test_18_scheduler_authority.py FFF....                      [ 87%]
planning/tests/contract/test_19_round_trip.py F..F.                                 [ 90%]
planning/tests/contract/test_16_transactions.py FF.FF...                            [ 94%]
planning/tests/contract/test_20_state_machine_torture.py .....                      [ 97%]
planning/tests/contract/test_00_contract_coverage.py ...FF                          [100%]

======================================== FAILURES =========================================
_ test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] _
planning/tests/contract/test_01_canonical_state.py:61: in test_required_existing_canonical_state_is_persisted
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' state. Expected one of ('manual_requested_date',); PlanningItem has {'canvas_object_type', 'parent', 'duration_category', 'priority_restore_context', 'schedule_is_manual', 'created_at', 'is_deleted', 'priority_position', 'planningitemtag', 'assignment_detail', 'due_date', 'children', 'is_completed', 'canvas_object_id', 'updated_at', 'tags', 'start_date', 'title', 'item_type', 'user', 'sibling_order', 'id', 'description', 'scheduled_date'}
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('manual_requested_date',))
___ test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] ___
planning/tests/contract/test_01_canonical_state.py:69: in test_required_new_canonical_state_exists
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expected one of ('percent_completed', 'completion_percent', 'progress_percent'). This is canonical user/domain state, not a scheduler-only value.
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('percent_completed', 'completion_percent', 'progress_percent'))
___________________ test_scheduled_date_and_anchor_are_distinct_fields ____________________
planning/tests/contract/test_01_canonical_state.py:79: in test_scheduled_date_and_anchor_are_distinct_fields
    assert "manual_requested_date" in names
E   AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________________ test_scheduler_date_can_change_without_destroying_anchor _________________
planning/tests/contract/test_01_canonical_state.py:89: in test_scheduler_date_can_change_without_destroying_anchor
    pytest.fail("MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent")
E   Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
____________ test_C2_child_creation_defaults_release_and_deadline_from_parent _____________
planning/tests/contract/test_03_creation.py:76: in test_C2_child_creation_defaults_release_and_deadline_from_parent
    assert child.start_date == parent.start_date, (
E   AssertionError: C2 MISSING: child creation must default release/start_date from parent
E   assert None == datetime.date(2026, 9, 22)
E    +  where None = <PlanningItem: [TASK] Child>.start_date
E    +  and   datetime.date(2026, 9, 22) = <PlanningItem: [TASK] Parent>.start_date
___ test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it ___
planning/tests/contract/test_03_creation.py:144: in test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it
    pytest.fail("C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor")
E   Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
____ test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion ____
planning/tests/contract/test_03_creation.py:180: in test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion
    assert parent.is_completed is False, (
E   AssertionError: C5 MISSING: a completed parent cannot remain semantically completed after an unfinished required child is added
E   assert True is False
E    +  where True = <PlanningItem: [TASK] Completed parent>.is_completed
______ test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress ______
planning/tests/contract/test_03_creation.py:192: in test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress
    pytest.fail(
E   Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable tasks
__________________ test_CR1_complete_atomic_leaf_leaves_active_frontier ___________________
planning/tests/contract/test_04_completion_reopen.py:49: in test_CR1_complete_atomic_leaf_leaves_active_frontier
    assert item.priority_position is not None
E   assert None is not None
E    +  where None = <PlanningItem: [TASK] Atomic>.priority_position
_____________ test_CR3_CR6_splittable_completion_has_canonical_progress_state _____________
planning/tests/contract/test_04_completion_reopen.py:123: in test_CR3_CR6_splittable_completion_has_canonical_progress_state
    assert field is not None, (
E   AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible completed progress-segment history for splittable tasks
E   assert None is not None
__________ test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed ___________
planning/tests/contract/test_04_completion_reopen.py:136: in test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed
    assert progress is not None, (
E   AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____________ test_CR4_reopening_one_progress_segment_requires_segment_identity ____________
planning/tests/contract/test_04_completion_reopen.py:155: in test_CR4_reopening_one_progress_segment_requires_segment_identity
    assert progress is not None, (
E   AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____ test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution ____
planning/tests/contract/test_04_completion_reopen.py:175: in test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it exists, completing B while prerequisite A is incomplete must require cancel OR explicit edge removal; ARC may not silently break A->B.
E   assert None is not None
_________ test_CR8_reopening_completed_prerequisite_requires_explicit_resolution __________
planning/tests/contract/test_04_completion_reopen.py:184: in test_CR8_reopening_completed_prerequisite_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopening prerequisite A while dependent B remains complete must require explicit conflict resolution rather than silently violating/removing A->B.
E   assert None is not None
__ test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child ___
planning/tests/contract/test_05_structural_frontier.py:146: in test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child
    assert field is not None, (
E   AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must exist before anchor suspension/inheritance can be implemented
E   assert None is not None
_________ test_H7_reversing_anchored_structural_transition_restores_parent_intent _________
planning/tests/contract/test_05_structural_frontier.py:174: in test_H7_reversing_anchored_structural_transition_restores_parent_intent
    assert field is not None, (
E   AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
E   assert None is not None
_______ test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent ________
planning/tests/contract/test_06_reparenting.py:146: in test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent
    assert dependency is not None, (
E   AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once present, reparenting an endpoint must preserve valid edges and reject/require explicit resolution for invalid semantics; it may never silently delete the dependency.
E   assert None is not None
_________________ test_D2_subtree_delete_requires_atomic_domain_semantics _________________
planning/tests/contract/test_07_delete_restore_undo.py:85: in test_D2_subtree_delete_requires_atomic_domain_semantics
    assert delete is not None, (
E   AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/subtree so active descendants/parent references cannot be left dangling by a partial multi-write operation
E   assert None is not None
___________ test_D3_deleting_dependency_endpoint_requires_edge_restore_history ____________
planning/tests/contract/test_07_delete_restore_undo.py:94: in test_D3_deleting_dependency_endpoint_requires_edge_restore_history
    assert dependency is not None, (
E   AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting an endpoint must suspend/remove incident active edges while retaining enough canonical/history context for safe restore.
E   assert None is not None
_____________ test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip _____________
planning/tests/contract/test_07_delete_restore_undo.py:103: in test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip
    assert restore is not None, (
E   AssertionError: D4 MISSING: restore must be a domain command that validates the original parent/dependency relationships against the current world; raw is_deleted=False is insufficient.
E   assert None is not None
_____________________ test_D5_restore_must_revalidate_hierarchy_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:112: in test_D5_restore_must_revalidate_hierarchy_cycle
    assert restore is not None, (
E   AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore must reject/redirect an original parent relationship that would now create a hierarchy cycle.
E   assert None is not None
____________________ test_D6_restore_must_revalidate_dependency_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:122: in test_D6_restore_must_revalidate_dependency_cycle
    assert restore is not None and dependency is not None, (
E   AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required. An old dependency edge may not be silently reactivated if it would create a dependency cycle in the present world.
E   assert (None is not None)
________ test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it _________
planning/tests/contract/test_07_delete_restore_undo.py:131: in test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it
    assert "manual_requested_date" in names, (
E   AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority ________
planning/tests/contract/test_09_dependencies.py:88: in test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_____________________ test_DP2_self_dependency_is_rejected_atomically _____________________
planning/tests/contract/test_09_dependencies.py:105: in test_DP2_self_dependency_is_rejected_atomically
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__________ test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges __________
planning/tests/contract/test_09_dependencies.py:120: in test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____________________ test_DP1_DP7_dependency_edits_are_tenant_isolated ____________________
planning/tests/contract/test_09_dependencies.py:137: in test_DP1_DP7_dependency_edits_are_tenant_isolated
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
________ test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier ________
planning/tests/contract/test_09_dependencies.py:148: in test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_________________ test_DP3_completing_prerequisite_may_unblock_dependant __________________
planning/tests/contract/test_09_dependencies.py:160: in test_DP3_completing_prerequisite_may_unblock_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
______________ test_DP4_reopening_prerequisite_reblocks_unfinished_dependant ______________
planning/tests/contract/test_09_dependencies.py:172: in test_DP4_reopening_prerequisite_reblocks_unfinished_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_ test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete _
planning/tests/contract/test_09_dependencies.py:187: in test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__ test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete __
planning/tests/contract/test_09_dependencies.py:205: in test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____ test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold _____
planning/tests/contract/test_09_dependencies.py:225: in test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold
    model, _ = _require_dependency_layer()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:54: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
______________ test_A1_valid_anchor_is_canonical_and_distinct_from_priority _______________
planning/tests/contract/test_11_anchors.py:81: in test_A1_valid_anchor_is_canonical_and_distinct_from_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
___________________ test_A2_moving_anchor_changes_canonical_anchor_date ___________________
planning/tests/contract/test_11_anchors.py:90: in test_A2_moving_anchor_changes_canonical_anchor_date
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__________ test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority ___________
planning/tests/contract/test_11_anchors.py:103: in test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change _____
planning/tests/contract/test_11_anchors.py:119: in test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change
    _set_anchor(item, due + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__ test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change ___
planning/tests/contract/test_11_anchors.py:141: in test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change
    _set_anchor(item, today + timedelta(days=1))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
______________ test_A6_passing_anchor_date_does_not_itself_make_task_overdue ______________
planning/tests/contract/test_11_anchors.py:158: in test_A6_passing_anchor_date_does_not_itself_make_task_overdue
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____ test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace _____
planning/tests/contract/test_11_anchors.py:172: in test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____________ test_A9_automatic_missed_schedule_is_not_converted_into_anchor ______________
planning/tests/contract/test_11_anchors.py:224: in test_A9_automatic_missed_schedule_is_not_converted_into_anchor
    assert getattr(item, _anchor_field()) is None
                         ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:31: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
__ test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor __
planning/tests/contract/test_11_anchors.py:231: in test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
_____________ test_A10_reversing_structural_episode_can_restore_parent_anchor _____________
planning/tests/contract/test_11_anchors.py:246: in test_A10_reversing_structural_episode_can_restore_parent_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:63: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:57: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer _____
planning/tests/contract/test_11_anchors.py:263: in test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer
    assert any(callable(getattr(service, n, None)) for n in names), (
E   AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user-created infeasible or overloaded plans
E   assert False
E    +  where False = any(<generator object test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer.<locals>.<genexpr> at 0x10ae67740>)
______ test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories _______
planning/tests/contract/test_12_duration_progress.py:105: in test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories
    assert EXPECTED_CLASSES <= values, (
E   AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >16h as distinct mutually-exclusive semantic classes. Current values: ['MIN_20_TO_60', 'OVER_60_MIN', 'UNDER_20_MIN']
E   assert {'OVER_16_HOU...NDER_8_HOURS'} <= {'MIN_20_TO_6...UNDER_20_MIN'}
E     
E     Extra items in the left set:
E     'UNDER_1_HOUR'
E     'UNDER_20_MINUTES'
E     'UNDER_4_HOURS'
E     'UNDER_16_HOURS'
E     'UNDER_8_HOURS'
E     'OVER_16_HOURS'
______ test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] ______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:127: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_______ test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed ________
planning/tests/contract/test_12_duration_progress.py:137: in test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
____________ test_E3_splittable_to_atomic_discards_partial_progress_semantics _____________
planning/tests/contract/test_12_duration_progress.py:150: in test_E3_splittable_to_atomic_discards_partial_progress_semantics
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_________ test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress _________
planning/tests/contract/test_12_duration_progress.py:166: in test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:91: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_____________ test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress _____________
planning/tests/contract/test_12_duration_progress.py:178: in test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress
    assert _get_progress(item) in (0, 0.0, None)
           ^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:98: in _get_progress
    return getattr(item, _progress_field())
                         ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:47: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_ test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal _
planning/tests/contract/test_12_duration_progress.py:210: in test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal
    assert model is not None, (
E   AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonical progress-segment/history identity so future scheduler proposals can change without rewriting confirmed progress
E   assert None is not None
________________ test_DUR009_reversing_one_completed_segment_can_be_local _________________
planning/tests/contract/test_12_duration_progress.py:220: in test_DUR009_reversing_one_completed_segment_can_be_local
    assert model is not None and service is not None, (
E   AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress service
E   assert (None is not None)
_____ test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations _____
planning/tests/contract/test_12_duration_progress.py:241: in test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations
    assert any(callable(getattr(service, n, None)) for n in complete_names)
E   assert False
E    +  where False = any(<generator object test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations.<locals>.<genexpr> at 0x10ae66440>)
___________ test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children ___________
planning/tests/contract/test_12_duration_progress.py:247: in test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children
    assert model is not None, "DUR-011 MISSING PREREQUISITE: progress segment model"
E   AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
E   assert None is not None
______ test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work ______
planning/tests/contract/test_13_large_allocations.py:96: in test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work
    assert model is not None, "ALLOC-001 MISSING: allocation/progress segment model"
E   AssertionError: ALLOC-001 MISSING: allocation/progress segment model
E   assert None is not None
______ test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress ______
planning/tests/contract/test_13_large_allocations.py:109: in test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______ test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress _______
planning/tests/contract/test_13_large_allocations.py:125: in test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress
    assert model is not None and service is not None
E   assert (None is not None)
_______________ test_L4_commenced_task_only_allocates_remaining_percentage ________________
planning/tests/contract/test_13_large_allocations.py:146: in test_L4_commenced_task_only_allocates_remaining_percentage
    assert model is not None
E   assert None is not None
____________ test_L5_reopening_one_completed_segment_reduces_only_its_progress ____________
planning/tests/contract/test_13_large_allocations.py:161: in test_L5_reopening_one_completed_segment_reduces_only_its_progress
    assert model is not None and service is not None
E   assert (None is not None)
_________________ test_L6_one_hundred_percent_reconciles_task_to_complete _________________
planning/tests/contract/test_13_large_allocations.py:175: in test_L6_one_hundred_percent_reconciles_task_to_complete
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
____________ test_L7_semantic_decomposition_does_not_fabricate_child_progress _____________
planning/tests/contract/test_13_large_allocations.py:196: in test_L7_semantic_decomposition_does_not_fabricate_child_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:55: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______________ test_L8_allocation_projection_is_not_semantic_planning_item _______________
planning/tests/contract/test_13_large_allocations.py:209: in test_L8_allocation_projection_is_not_semantic_planning_item
    assert model is not None
E   assert None is not None
_________________________ test_F1_focus_projection_service_exists _________________________
planning/tests/contract/test_14_focus.py:56: in test_F1_focus_projection_service_exists
    assert service is not None, "FOC-001 MISSING: Focus projection/service"
E   AssertionError: FOC-001 MISSING: Focus projection/service
E   assert None is not None
__________ test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket __________
planning/tests/contract/test_14_focus.py:62: in test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket
    assert service is not None
E   assert None is not None
_________________ test_F2_lookahead_is_read_only_and_does_not_reschedule __________________
planning/tests/contract/test_14_focus.py:71: in test_F2_lookahead_is_read_only_and_does_not_reschedule
    assert service is not None
E   assert None is not None
_________________ test_F3_F4_selecting_current_focus_is_convenience_only __________________
planning/tests/contract/test_14_focus.py:97: in test_F3_F4_selecting_current_focus_is_convenience_only
    assert service is not None
E   assert None is not None
__________________ test_F5_do_today_translates_to_explicit_today_anchor ___________________
planning/tests/contract/test_14_focus.py:117: in test_F5_do_today_translates_to_explicit_today_anchor
    assert service is not None
E   assert None is not None
__________ test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent __________
planning/tests/contract/test_14_focus.py:136: in test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent
    assert service is not None
E   assert None is not None
____________ test_F7_explicit_focus_reprioritise_uses_global_priority_service _____________
planning/tests/contract/test_14_focus.py:155: in test_F7_explicit_focus_reprioritise_uses_global_priority_service
    assert service is not None
E   assert None is not None
___________________ test_F8_wrong_visual_bucket_cannot_mutate_duration ____________________
planning/tests/contract/test_14_focus.py:167: in test_F8_wrong_visual_bucket_cannot_mutate_duration
    assert service is not None
E   assert None is not None
________ test_F9_non_executable_current_focus_is_cleared_without_planning_mutation ________
planning/tests/contract/test_14_focus.py:177: in test_F9_non_executable_current_focus_is_cleared_without_planning_mutation
    assert service is not None
E   assert None is not None
______ test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections _______
planning/tests/contract/test_17_view_coherence.py:124: in test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections
    move(*args)
/opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:85: in inner
    return func(*args, **kwds)
           ^^^^^^^^^^^^^^^^^^^
planning/services/priority.py:225: in reorder
    raise ValidationError('That task is not in the priority order.')
E   django.core.exceptions.ValidationError: ['That task is not in the priority order.']
____________ test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop _____________
planning/tests/contract/test_17_view_coherence.py:142: in test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop
    assert "manual_requested_date" in fields, (
E   AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
____________ test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning _____________
planning/tests/contract/test_17_view_coherence.py:192: in test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning
    assert service is not None, "VIEW-003 prerequisite: Focus projection"
E   AssertionError: VIEW-003 prerequisite: Focus projection
E   assert None is not None
___________ test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts ____________
planning/tests/contract/test_17_view_coherence.py:234: in test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts
    assert service is not None
E   assert None is not None
___________ test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes ____________
planning/tests/contract/test_17_view_coherence.py:263: in test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes
    assert commands is not None, (
E   AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boundary rather than separate serializer/view databases
E   assert None is not None
___________________ test_AUTH_001_hard_anchor_survives_scheduler_rerun ____________________
planning/tests/contract/test_18_scheduler_authority.py:84: in test_AUTH_001_hard_anchor_survives_scheduler_rerun
    assert "manual_requested_date" in fields, (
E   AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
_______________ test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts _______________
planning/tests/contract/test_18_scheduler_authority.py:118: in test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts
    assert _canonical(item) == before, (
E   AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may not
E   assert {'title': 'Ca...': False, ...} == {'title': 'Ca...': False, ...}
E     
E     Omitting 8 identical items, use -vv to show
E     Differing items:
E     {'priority_position': 1} != {'priority_position': None}
E     Use -v to get more diff
____________ test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges _____________
planning/tests/contract/test_18_scheduler_authority.py:127: in test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges
    assert dependency is not None, (
E   AssertionError: AUTH-002 prerequisite: dependency graph implementation
E   assert None is not None
____________ test_RT_001_delete_restore_round_trip_preserves_semantic_identity ____________
planning/tests/contract/test_19_round_trip.py:78: in test_RT_001_delete_restore_round_trip_preserves_semantic_identity
    assert delete is not None and restore is not None, (
E   AssertionError: RT-001 prerequisite: validated delete + restore domain commands
E   assert (None is not None)
____________ test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts ____________
planning/tests/contract/test_19_round_trip.py:163: in test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts
    assert "manual_requested_date" in fields, (
E   AssertionError: RT-004 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit _________
planning/tests/contract/test_16_transactions.py:51: in test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit
    assert commands is not None, (
E   AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather than independent serializer/model writes
E   assert None is not None
_________________ test_X1_failed_multi_field_edit_rolls_back_every_field __________________
planning/tests/contract/test_16_transactions.py:63: in test_X1_failed_multi_field_edit_rolls_back_every_field
    assert commands is not None
E   assert None is not None
___________ test_X3_risky_overload_needs_confirmation_capability_before_commit ____________
planning/tests/contract/test_16_transactions.py:95: in test_X3_risky_overload_needs_confirmation_capability_before_commit
    assert commands is not None
E   assert None is not None
________ test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised _________
planning/tests/contract/test_16_transactions.py:104: in test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised
    assert commands is not None
E   assert None is not None
_____________ test_each_contract_area_is_claimed_by_its_designated_test_file ______________
planning/tests/contract/test_00_contract_coverage.py:104: in test_each_contract_area_is_claimed_by_its_designated_test_file
    assert not problems, (
E   AssertionError: Some frozen requirements have no test in their designated module: {'test_01_canonical_state.py': {'missing_contract_ids': ['CAN-001', 'CAN-002', 'CAN-003', 'CAN-004', 'CAN-005', 'CAN-006', 'CAN-007', 'CAN-008', 'CAN-009', 'CAN-010']}, 'test_02_invariants.py': {'missing_contract_ids': ['HIE-001', 'HIE-002']}, 'test_03_creation.py': {'missing_contract_ids': ['CRE-001', 'CRE-002', 'CRE-003', 'CRE-004', 'CRE-005', 'CRE-006', 'CRE-007']}, 'test_04_completion_reopen.py': {'missing_contract_ids': ['CMP-001', 'CMP-002', 'CMP-003', 'CMP-004', 'CMP-005', 'CMP-006']}, 'test_05_structural_frontier.py': {'missing_contract_ids': ['HIE-003', 'HIE-004', 'HIE-005', 'HIE-006', 'HIE-007', 'HIE-008']}, 'test_06_reparenting.py': {'missing_contract_ids': ['REP-001', 'REP-002', 'REP-003', 'REP-004', 'REP-005']}, 'test_07_delete_restore_undo.py': {'missing_contract_ids': ['DEL-001', 'DEL-002', 'DEL-003', 'DEL-004', 'DEL-005', 'DEL-006']}, 'test_08_priority.py': {'missing_contract_ids': ['PRI-001', 'PRI-002', 'PRI-003', 'PRI-004', 'PRI-005', 'PRI-006', 'PRI-007', 'PRI-008']}, 'test_09_dependencies.py': {'missing_contract_ids': ['DEP-001', 'DEP-002', 'DEP-003', 'DEP-004', 'DEP-005', 'DEP-006', 'DEP-007', 'DEP-008', 'DEP-009', 'DEP-010']}, 'test_10_temporal.py': {'missing_contract_ids': ['TMP-001', 'TMP-002', 'TMP-003', 'TMP-004', 'TMP-005', 'TMP-006', 'TMP-007', 'TMP-008', 'TMP-009', 'TMP-010', 'TMP-011']}, 'test_11_anchors.py': {'missing_contract_ids': ['ANC-001', 'ANC-002', 'ANC-003', 'ANC-004', 'ANC-005', 'ANC-006', 'ANC-007', 'ANC-008', 'ANC-009', 'ANC-010', 'ANC-011', 'ANC-012']}, 'test_12_duration_progress.py': {'missing_contract_ids': ['DUR-001', 'DUR-002', 'DUR-003', 'DUR-004', 'DUR-005', 'DUR-006', 'DUR-007', 'DUR-008', 'DUR-009', 'DUR-010', 'DUR-011']}, 'test_13_large_allocations.py': {'missing_contract_ids': ['ALL-001', 'ALL-002', 'ALL-003', 'ALL-004', 'ALL-005', 'ALL-006', 'ALL-007', 'ALL-008']}, 'test_14_focus.py': {'missing_contract_ids': ['FOC-001', 'FOC-002', 'FOC-003', 'FOC-004', 'FOC-005', 'FOC-006', 'FOC-007', 'FOC-008', 'FOC-009', 'FOC-010']}, 'test_15_scheduler_timeline.py': {'missing_contract_ids': ['SCH-001', 'SCH-002', 'SCH-003', 'SCH-004', 'SCH-005', 'SCH-006', 'SCH-007', 'SCH-008', 'SCH-009', 'SCH-010', 'SCH-011', 'SCH-012', 'SCH-013']}, 'test_16_transactions.py': {'missing_contract_ids': ['TRX-001', 'TRX-002', 'TRX-003']}, 'test_17_view_coherence.py': {'missing_contract_ids': ['VIEW-001', 'VIEW-002', 'VIEW-003']}, 'test_18_scheduler_authority.py': {'missing_contract_ids': ['AUTH-001', 'AUTH-002', 'AUTH-003', 'AUTH-004']}, 'test_19_round_trip.py': {'missing_contract_ids': ['RT-001', 'RT-002', 'RT-003', 'RT-004', 'RT-005', 'RT-006']}, 'test_20_state_machine_torture.py': {'missing_contract_ids': ['RT-001', 'RT-002', 'RT-003', 'RT-004', 'RT-005', 'RT-006']}}
E   assert not {'test_01_canonical_state.py': {'missing_contract_ids': ['CAN-001', 'CAN-002', 'CAN-003', 'CAN-004', 'CAN-005', 'CAN-0...mpletion_reopen.py': {'missing_contract_ids': ['CMP-001', 'CMP-002', 'CMP-003', 'CMP-004', 'CMP-005', 'CMP-006']}, ...}
___________________ test_every_frozen_requirement_is_covered_somewhere ____________________
planning/tests/contract/test_00_contract_coverage.py:113: in test_every_frozen_requirement_is_covered_somewhere
    assert not missing, (
E   AssertionError: Contract requirements without executable tests: ALL-001, ALL-002, ALL-003, ALL-004, ALL-005, ALL-006, ALL-007, ALL-008, ANC-001, ANC-002, ANC-003, ANC-004, ANC-005, ANC-006, ANC-007, ANC-008, ANC-009, ANC-010, ANC-011, ANC-012, AUTH-001, AUTH-002, AUTH-003, AUTH-004, CAN-001, CAN-002, CAN-003, CAN-004, CAN-005, CAN-006, CAN-007, CAN-008, CAN-009, CAN-010, CMP-001, CMP-002, CMP-003, CMP-004, CMP-005, CMP-006, CRE-001, CRE-002, CRE-003, CRE-004, CRE-005, CRE-006, CRE-007, DEL-001, DEL-002, DEL-003, DEL-004, DEL-005, DEL-006, DEP-001, DEP-002, DEP-003, DEP-004, DEP-005, DEP-006, DEP-007, DEP-008, DEP-009, DEP-010, DUR-001, DUR-002, DUR-003, DUR-004, DUR-005, DUR-006, DUR-007, DUR-008, DUR-009, DUR-010, DUR-011, FOC-001, FOC-002, FOC-003, FOC-004, FOC-005, FOC-006, FOC-007, FOC-008, FOC-009, FOC-010, HIE-001, HIE-002, HIE-003, HIE-004, HIE-005, HIE-006, HIE-007, HIE-008, PRI-001, PRI-002, PRI-003, PRI-004, PRI-005, PRI-006, PRI-007, PRI-008, REP-001, REP-002, REP-003, REP-004, REP-005, RT-001, RT-002, RT-003, RT-004, RT-005, RT-006, SCH-001, SCH-002, SCH-003, SCH-004, SCH-005, SCH-006, SCH-007, SCH-008, SCH-009, SCH-010, SCH-011, SCH-012, SCH-013, TMP-001, TMP-002, TMP-003, TMP-004, TMP-005, TMP-006, TMP-007, TMP-008, TMP-009, TMP-010, TMP-011, TRX-001, TRX-002, TRX-003, VIEW-001, VIEW-002, VIEW-003
E   assert not ['ALL-001', 'ALL-002', 'ALL-003', 'ALL-004', 'ALL-005', 'ALL-006', ...]
================================= short test summary info =================================
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] - AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' s...
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] - AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expect...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduled_date_and_anchor_are_distinct_fields - AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduler_date_can_change_without_destroying_anchor - Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
FAILED planning/tests/contract/test_03_creation.py::test_C2_child_creation_defaults_release_and_deadline_from_parent - AssertionError: C2 MISSING: child creation must default release/start_date from parent
FAILED planning/tests/contract/test_03_creation.py::test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it - Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_03_creation.py::test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion - AssertionError: C5 MISSING: a completed parent cannot remain semantically completed af...
FAILED planning/tests/contract/test_03_creation.py::test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress - Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable t...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR1_complete_atomic_leaf_leaves_active_frontier - assert None is not None
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_CR6_splittable_completion_has_canonical_progress_state - AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible comple...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed - AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR4_reopening_one_progress_segment_requires_segment_identity - AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution - AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR8_reopening_completed_prerequisite_requires_explicit_resolution - AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopeni...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child - AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must e...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H7_reversing_anchored_structural_transition_restores_parent_intent - AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_06_reparenting.py::test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent - AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once pr...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D2_subtree_delete_requires_atomic_domain_semantics - AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D3_deleting_dependency_endpoint_requires_edge_restore_history - AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip - AssertionError: D4 MISSING: restore must be a domain command that validates the origin...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D5_restore_must_revalidate_hierarchy_cycle - AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore ...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D6_restore_must_revalidate_dependency_cycle - AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required....
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it - AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP2_self_dependency_is_rejected_atomically - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_DP7_dependency_edits_are_tenant_isolated - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP3_completing_prerequisite_may_unblock_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_reopening_prerequisite_reblocks_unfinished_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_11_anchors.py::test_A1_valid_anchor_is_canonical_and_distinct_from_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A2_moving_anchor_changes_canonical_anchor_date - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A6_passing_anchor_date_does_not_itself_make_task_overdue - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_automatic_missed_schedule_is_not_converted_into_anchor - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A10_reversing_structural_episode_can_restore_parent_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer - AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories - AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E3_splittable_to_atomic_discards_partial_progress_semantics - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal - AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonic...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR009_reversing_one_completed_segment_can_be_local - AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress ser...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations - assert False
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children - AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work - AssertionError: ALLOC-001 MISSING: allocation/progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L4_commenced_task_only_allocates_remaining_percentage - assert None is not None
FAILED planning/tests/contract/test_13_large_allocations.py::test_L5_reopening_one_completed_segment_reduces_only_its_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L6_one_hundred_percent_reconciles_task_to_complete - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L7_semantic_decomposition_does_not_fabricate_child_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L8_allocation_projection_is_not_semantic_planning_item - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_projection_service_exists - AssertionError: FOC-001 MISSING: Focus projection/service
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F2_lookahead_is_read_only_and_does_not_reschedule - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F3_F4_selecting_current_focus_is_convenience_only - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F5_do_today_translates_to_explicit_today_anchor - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F7_explicit_focus_reprioritise_uses_global_priority_service - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F8_wrong_visual_bucket_cannot_mutate_duration - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F9_non_executable_current_focus_is_cleared_without_planning_mutation - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections - django.core.exceptions.ValidationError: ['That task is not in the priority order.']
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop - AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning - AssertionError: VIEW-003 prerequisite: Focus projection
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes - AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boun...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_001_hard_anchor_survives_scheduler_rerun - AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts - AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges - AssertionError: AUTH-002 prerequisite: dependency graph implementation
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_001_delete_restore_round_trip_preserves_semantic_identity - AssertionError: RT-001 prerequisite: validated delete + restore domain commands
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts - AssertionError: RT-004 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_16_transactions.py::test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit - AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather ...
FAILED planning/tests/contract/test_16_transactions.py::test_X1_failed_multi_field_edit_rolls_back_every_field - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X3_risky_overload_needs_confirmation_capability_before_commit - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised - assert None is not None
FAILED planning/tests/contract/test_00_contract_coverage.py::test_each_contract_area_is_claimed_by_its_designated_test_file - AssertionError: Some frozen requirements have no test in their designated module: {'te...
FAILED planning/tests/contract/test_00_contract_coverage.py::test_every_frozen_requirement_is_covered_somewhere - AssertionError: Contract requirements without executable tests: ALL-001, ALL-002, ALL-...
============================= 89 failed, 96 passed in 41.57s ==============================
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % cp -R planning/tests/contract planning/tests/contract.backup
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % >....                                                                           
    tree = ast.parse(text)
    functions = {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    missing = sorted(set(mapping) - set(functions))
    if missing:
        raise SystemExit(f"{filename}: missing expected tests: {missing}")

    # Import the decorator if this file doesn't already do so.
    if "from .conftest import covers" not in text:
        lines = text.splitlines(keepends=True)

        # Put after __future__ import when present.
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from __future__ import"):
                insert_at = i + 1
                break

        lines.insert(insert_at, "\nfrom .conftest import covers\n")
        text = "".join(lines)

    # Reparse after import insertion.
    tree = ast.parse(text)
    functions = {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    lines = text.splitlines(keepends=True)

    # Insert bottom-up so line numbers remain valid.
    inserts = []
    for fn_name, ids in mapping.items():
        node = functions[fn_name]

        # Don't duplicate if rerun.
        already = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                f = dec.func
                if (isinstance(f, ast.Name) and f.id == "covers") or (
                    isinstance(f, ast.Attribute) and f.attr == "covers"
                ):
                    already = True
                    break

        if not already:
            decorator = "@covers(" + ", ".join(repr(x) for x in ids) + ")\n"
            inserts.append((node.lineno - 1, decorator))

    for index, decorator in sorted(inserts, reverse=True):
        lines.insert(index, decorator)

    path.write_text("".join(lines), encoding="utf-8")
    print(f"patched {filename}")

print("\nDone: @covers metadata added.")
PY
patched test_01_canonical_state.py
patched test_02_invariants.py
patched test_03_creation.py
patched test_04_completion_reopen.py
patched test_05_structural_frontier.py
patched test_06_reparenting.py
patched test_07_delete_restore_undo.py
patched test_08_priority.py
patched test_09_dependencies.py
patched test_10_temporal.py
patched test_11_anchors.py
patched test_12_duration_progress.py
patched test_13_large_allocations.py
patched test_14_focus.py
patched test_15_scheduler_timeline.py
patched test_16_transactions.py
patched test_17_view_coherence.py
patched test_18_scheduler_authority.py
patched test_19_round_trip.py
patched test_20_state_machine_torture.py

Done: @covers metadata added.
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python - <<'PY'
from pathlib import Path

p = Path("planning/tests/contract/test_00_contract_coverage.py")
s = p.read_text()

start = s.index(
    "def test_each_contract_area_is_claimed_by_its_designated_test_file():"
)
end = s.index(
    "\ndef test_every_frozen_requirement_is_covered_somewhere():",
    start,
)

replacement = '''def test_each_contract_area_is_claimed_by_its_designated_test_file():
    """Each contract area must be covered across its designated test module(s).

    Multiple files may intentionally share an area.  For example, round-trip
    behaviour is split between test_19_round_trip.py and
    test_20_state_machine_torture.py, so their claims must be combined rather
    than requiring both files to duplicate every RT requirement.
    """
    area_files: dict[str, set[str]] = {}

    for filename, areas in TEST_FILE_AREAS.items():
        for area in areas:
            area_files.setdefault(area, set()).add(filename)

    problems: dict[str, dict[str, list[str]]] = {}

    for area, filenames in area_files.items():
        claimed: set[str] = set()

        for filename in filenames:
            path = CONTRACT_DIR / filename
            if not path.exists():
                # The existence test provides the cleaner primary failure.
                continue
            claimed |= _literal_contract_ids_from_file(path)

        required = ids_for_area(area)
        missing = sorted(required - claimed)

        if missing:
            problems[area] = {
                "designated_files": sorted(filenames),
                "missing_contract_ids": missing,
            }

    assert not problems, (
        "Some frozen requirements have no test in their designated contract "
        f"area: {problems}"
    )

'''

p.write_text(s[:start] + replacement + s[end:])
print("patched test_00_contract_coverage.py")
PY
patched test_00_contract_coverage.py
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % pytest planning/tests/contract/test_00_contract_coverage.py -q
ImportError while loading conftest '/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend/conftest.py'.
conftest.py:4: in <module>
    from django.core.cache import cache
E   ModuleNotFoundError: No module named 'django'
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % cd backend

which python
python -c "import sys, django; print('PYTHON:', sys.executable); print('DJANGO:', django.__version__, django.__file__)"
cd: no such file or directory: backend
/Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/bin/python
PYTHON: /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/bin/python
DJANGO: 6.1.1 /Users/rajdipshah/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/.venv/lib/python3.14/site-packages/django/__init__.py
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % >....                                                                           
            if callable(getattr(dependency_service, name, None))
        ),
        None,
    )
    assert add is not None, "DEP-009 prerequisite: dependency creation command"

    prerequisite = make_item(user, "Prerequisite")
    dependant = make_item(user, "Dependant")

    created = False
    for args in (
        (user, dependant, prerequisite),
        (dependant, prerequisite),
        (user, dependant.pk, prerequisite.pk),
        (dependant.pk, prerequisite.pk),
    ):
        try:
            add(*args)
            created = True
            break
        except TypeError:
            continue

    assert created, "DEP-009: dependency command has no supported domain signature"

    scheduler = _scheduler_service() if "_scheduler_service" in globals() else None
    if scheduler is None:
        for module_name in (
            "planning.services.scheduling",
            "planning.services.scheduler",
        ):
            try:
                scheduler = importlib.import_module(module_name)
                break
            except ModuleNotFoundError:
                continue

    assert scheduler is not None, "DEP-009 prerequisite: scheduler service"

    fn = next(
        (
            getattr(scheduler, name)
            for name in ("schedule", "reschedule", "run", "reconcile_schedule")
            if callable(getattr(scheduler, name, None))
        ),
        None,
    )
    assert fn is not None

    try:
        fn(user)
    except TypeError:
        fn(user, today)

    dependant.refresh_from_db()
    prerequisite.refresh_from_db()

    # An incomplete prerequisite must prevent executable placement of dependant.
    assert prerequisite.is_completed or dependant.scheduled_date is None, (
        "DEP-009: scheduler placed a dependant while its hard prerequisite "
        "remained incomplete."
    )
PY
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % >....                                                                           
    due = today + timedelta(days=3)
    item = make_item(
        user,
        "Deadline constrained",
        start_date=release,
        due_date=due,
    )

    _reschedule(user, today)
    placed = _scheduled_date(item)

    assert placed is None or release <= placed <= due, (
        "TMP-006: scheduler must preserve legal capacity/window for "
        "deadline-constrained work where placement is possible."
    )

@covers("TMP-007")
def test_TMP007_scheduler_never_solves_pressure_by_automatic_deadline_violation(
    user, make_item, today
):
    items = [
        make_item(
            user,
            f"Pressure {i}",
            start_date=today,
            due_date=today + timedelta(days=1),
            duration_category="UNDER_4_HOURS",
        )
        for i in range(4)
    ]

    _reschedule(user, today)

    for item in items:
        item.refresh_from_db()
        assert item.scheduled_date is None or item.scheduled_date <= item.due_date, (
            "TMP-007: controlled overload/infeasibility is preferable to "
            "silently scheduling work after its deadline."
        )

@covers("TMP-008")
def test_TMP008_scheduler_avoids_deadline_day_when_safer_earlier_day_is_feasible(
    user, make_item, today
):
    item = make_item(
        user,
        "Deadline risk",
        start_date=today,
        due_date=today + timedelta(days=4),
        duration_category="UNDER_4_HOURS",
    )

    _reschedule(user, today)
    placed = _scheduled_date(item)

    assert placed is not None
    assert placed < item.due_date, (
        "TMP-008: with safe earlier capacity available, automatic scheduling "
        "must avoid deadline-day placement."
    )
PY
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % >....                                                                           

    assert tiny.duration_category != huge.duration_category

    service = _service()
    assert service is not None

    # The contract does not freeze an exact pressure formula, only that
    # scheduling capacity is not reducible to number-of-tasks.
    source_names = {
        name.lower()
        for name in dir(service)
    }
    assert (
        any(
            token in name
            for name in source_names
            for token in ("duration", "effort", "capacity", "load", "allocation")
        )
        or hasattr(service, "schedule")
        or hasattr(service, "reschedule")
    ), "SCH-008: scheduler exposes no effort/capacity scheduling semantics"

@covers("SCH-009")
def test_SCH009_frozen_mvp_has_no_user_weekday_availability_calendar():
    """ARC does not ask users to maintain recurring weekday work capacity."""
    fields = {f.name for f in PlanningItem._meta.get_fields()}

    forbidden = {
        "weekday_capacity",
        "daily_capacity",
        "availability_calendar",
        "working_days",
        "weekly_availability",
    }

    assert not (fields & forbidden), (
        "SCH-009: frozen MVP must not require a user-maintained weekday "
        f"capacity calendar. Found: {sorted(fields & forbidden)}"
    )

@covers("SCH-012")
def test_SCH012_pressure_bands_are_projection_not_frozen_canonical_task_state():
    """Chill/Busy/Stacked/Crunch/Infeasible are derived scheduler projections."""
    fields = {f.name for f in PlanningItem._meta.get_fields()}

    forbidden = {
        "pressure_band",
        "pressure_state",
        "workload_band",
    }

    assert not (fields & forbidden), (
        "SCH-012: pressure bands are derived/projected scheduling information, "
        "not canonical PlanningItem facts with frozen thresholds."
    )

    service = _service()
    assert service is not None, (
        "SCH-012: scheduler service must own/project workload pressure."
    )
PY
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python - <<'PY'
from pathlib import Path

root = Path("planning/tests/contract")

for p in sorted(root.glob("test_*.py")):
    if p.name == "test_00_contract_coverage.py":
        continue

    s = p.read_text()

    if "@covers(" not in s:
        continue

    if "from .conftest import covers" in s:
        continue

    marker = "from __future__ import annotations\n"

    if marker in s:
        s = s.replace(
            marker,
            marker + "\nfrom .conftest import covers\n",
            1,
        )
    else:
        # Put after module docstring/import preamble safely enough for these files.
        lines = s.splitlines(True)
        insertion = 0

        if lines and lines[0].lstrip().startswith(('"""', "'''")):
            quote = '"""' if '"""' in lines[0] else "'''"
            if lines[0].count(quote) >= 2:
                insertion = 1
            else:
                for i in range(1, len(lines)):
                    if quote in lines[i]:
                        insertion = i + 1
                        break

        lines.insert(insertion, "\nfrom .conftest import covers\n")
        s = "".join(lines)

    p.write_text(s)
    print("added covers import:", p.name)
PY
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m compileall -q planning/tests/contract
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m pytest planning/tests/contract/test_00_contract_coverage.py -q
...FF                                                                               [100%]
======================================== FAILURES =========================================
_____________ test_each_contract_area_is_claimed_by_its_designated_test_file ______________
planning/tests/contract/test_00_contract_coverage.py:124: in test_each_contract_area_is_claimed_by_its_designated_test_file
    assert not problems, (
E   AssertionError: Some frozen requirements have no test in their designated contract area: {'canonical_state': {'designated_files': ['test_01_canonical_state.py'], 'missing_contract_ids': ['CAN-005', 'CAN-010']}}
E   assert not {'canonical_state': {'designated_files': ['test_01_canonical_state.py'], 'missing_contract_ids': ['CAN-005', 'CAN-010']}}
___________________ test_every_frozen_requirement_is_covered_somewhere ____________________
planning/tests/contract/test_00_contract_coverage.py:133: in test_every_frozen_requirement_is_covered_somewhere
    assert not missing, (
E   AssertionError: Contract requirements without executable tests: CAN-005, CAN-010
E   assert not ['CAN-005', 'CAN-010']
================================= short test summary info =================================
FAILED planning/tests/contract/test_00_contract_coverage.py::test_each_contract_area_is_claimed_by_its_designated_test_file - AssertionError: Some frozen requirements have no test in their designated contract are...
FAILED planning/tests/contract/test_00_contract_coverage.py::test_every_frozen_requirement_is_covered_somewhere - AssertionError: Contract requirements without executable tests: CAN-005, CAN-010
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m pytest planning/tests/contract/test_00_contract_coverage.py -q
...FF                                                                               [100%]
======================================== FAILURES =========================================
_____________ test_each_contract_area_is_claimed_by_its_designated_test_file ______________
planning/tests/contract/test_00_contract_coverage.py:124: in test_each_contract_area_is_claimed_by_its_designated_test_file
    assert not problems, (
E   AssertionError: Some frozen requirements have no test in their designated contract area: {'canonical_state': {'designated_files': ['test_01_canonical_state.py'], 'missing_contract_ids': ['CAN-005', 'CAN-010']}}
E   assert not {'canonical_state': {'designated_files': ['test_01_canonical_state.py'], 'missing_contract_ids': ['CAN-005', 'CAN-010']}}
___________________ test_every_frozen_requirement_is_covered_somewhere ____________________
planning/tests/contract/test_00_contract_coverage.py:133: in test_every_frozen_requirement_is_covered_somewhere
    assert not missing, (
E   AssertionError: Contract requirements without executable tests: CAN-005, CAN-010
E   assert not ['CAN-005', 'CAN-010']
================================= short test summary info =================================
FAILED planning/tests/contract/test_00_contract_coverage.py::test_each_contract_area_is_claimed_by_its_designated_test_file - AssertionError: Some frozen requirements have no test in their designated contract are...
FAILED planning/tests/contract/test_00_contract_coverage.py::test_every_frozen_requirement_is_covered_somewhere - AssertionError: Contract requirements without executable tests: CAN-005, CAN-010
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % cat >> planning/tests/contract/test_01_canonical_state.py <<'PY'

@covers("CAN-005")
def test_CAN005_convenience_ui_state_does_not_become_canonical_planning_truth():
    """Convenience/UI projection state must not become canonical planning truth."""
    from planning.models import PlanningItem

    fields = {field.name for field in PlanningItem._meta.get_fields()}

    forbidden_ui_state = {
        "is_current_focus",
        "current_focus",
        "focus_selected",
        "focus_bucket",
        "visual_bucket",
        "planner_view_order",
        "timeline_view_order",
        "focus_view_order",
    }

    leaked = fields & forbidden_ui_state

    assert not leaked, (
        "CAN-005: view/convenience state must not become an independent "
        f"canonical planning truth. Found canonical fields: {sorted(leaked)}"
    )

@covers("CAN-010")
def test_CAN010_canonical_planning_mutations_have_shared_domain_command_boundary():
    """Canonical mutations must have a shared domain-command/service boundary."""
    from pathlib import Path

    planning_root = Path(__file__).resolve().parents[2]

    candidate_boundaries = (
        planning_root / "services",
        planning_root / "domain",
        planning_root / "commands.py",
        planning_root / "domain_commands.py",
    )

    assert any(path.exists() for path in candidate_boundaries), (
        "CAN-010: ARC requires a shared domain command/service boundary "
        "through which canonical planning mutations can be reconciled."
    )

    services = planning_root / "services"

    if services.exists():
        service_modules = {
            path.stem
            for path in services.glob("*.py")
            if path.name != "__init__.py"
        }

        assert service_modules, (
            "CAN-010: planning/services exists but exposes no domain services."
        )
PY
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % grep -nE 'CAN-005|CAN-010' \
  planning/tests/contract/test_01_canonical_state.py
168:@covers("CAN-005")
189:        "CAN-005: view/convenience state must not become an independent "
194:@covers("CAN-010")
209:        "CAN-010: ARC requires a shared domain command/service boundary "
223:            "CAN-010: planning/services exists but exposes no domain services."
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m compileall -q planning/tests/contract &&
python -m pytest planning/tests/contract/test_00_contract_coverage.py -q
.....                                                                               [100%]
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % python -m pytest planning/tests/contract -q
.F......FFF................F..FFFF...FFFFF........FF.....F.FFFFFF............FFFFFF [ 42%]
FFFFF.............FFFFFFFFFFFFF...FFFFFFF..FFFFFFFFFFFFFFFFFFFFF.............FFFFFF [ 85%]
FF....F..F.FF.FF.............                                                       [100%]
======================================== FAILURES =========================================
_ test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] _
planning/tests/contract/test_01_canonical_state.py:64: in test_required_existing_canonical_state_is_persisted
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' state. Expected one of ('manual_requested_date',); PlanningItem has {'duration_category', 'item_type', 'parent', 'canvas_object_type', 'due_date', 'canvas_object_id', 'start_date', 'is_completed', 'planningitemtag', 'priority_restore_context', 'title', 'id', 'tags', 'schedule_is_manual', 'is_deleted', 'updated_at', 'assignment_detail', 'sibling_order', 'children', 'description', 'created_at', 'priority_position', 'user', 'scheduled_date'}
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('manual_requested_date',))
___ test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] ___
planning/tests/contract/test_01_canonical_state.py:73: in test_required_new_canonical_state_exists
    assert _has_any_field(PlanningItem, candidates), (
E   AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expected one of ('percent_completed', 'completion_percent', 'progress_percent'). This is canonical user/domain state, not a scheduler-only value.
E   assert False
E    +  where False = _has_any_field(PlanningItem, ('percent_completed', 'completion_percent', 'progress_percent'))
___________________ test_scheduled_date_and_anchor_are_distinct_fields ____________________
planning/tests/contract/test_01_canonical_state.py:84: in test_scheduled_date_and_anchor_are_distinct_fields
    assert "manual_requested_date" in names
E   AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________________ test_scheduler_date_can_change_without_destroying_anchor _________________
planning/tests/contract/test_01_canonical_state.py:95: in test_scheduler_date_can_change_without_destroying_anchor
    pytest.fail("MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent")
E   Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
____________ test_C2_child_creation_defaults_release_and_deadline_from_parent _____________
planning/tests/contract/test_03_creation.py:80: in test_C2_child_creation_defaults_release_and_deadline_from_parent
    assert child.start_date == parent.start_date, (
E   AssertionError: C2 MISSING: child creation must default release/start_date from parent
E   assert None == datetime.date(2026, 9, 22)
E    +  where None = <PlanningItem: [TASK] Child>.start_date
E    +  and   datetime.date(2026, 9, 22) = <PlanningItem: [TASK] Parent>.start_date
___ test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it ___
planning/tests/contract/test_03_creation.py:151: in test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it
    pytest.fail("C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor")
E   Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
____ test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion ____
planning/tests/contract/test_03_creation.py:188: in test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion
    assert parent.is_completed is False, (
E   AssertionError: C5 MISSING: a completed parent cannot remain semantically completed after an unfinished required child is added
E   assert True is False
E    +  where True = <PlanningItem: [TASK] Completed parent>.is_completed
______ test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress ______
planning/tests/contract/test_03_creation.py:201: in test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress
    pytest.fail(
E   Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable tasks
__________________ test_CR1_complete_atomic_leaf_leaves_active_frontier ___________________
planning/tests/contract/test_04_completion_reopen.py:52: in test_CR1_complete_atomic_leaf_leaves_active_frontier
    assert item.priority_position is not None
E   assert None is not None
E    +  where None = <PlanningItem: [TASK] Atomic>.priority_position
_____________ test_CR3_CR6_splittable_completion_has_canonical_progress_state _____________
planning/tests/contract/test_04_completion_reopen.py:128: in test_CR3_CR6_splittable_completion_has_canonical_progress_state
    assert field is not None, (
E   AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible completed progress-segment history for splittable tasks
E   assert None is not None
__________ test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed ___________
planning/tests/contract/test_04_completion_reopen.py:141: in test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed
    assert progress is not None, (
E   AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____________ test_CR4_reopening_one_progress_segment_requires_segment_identity ____________
planning/tests/contract/test_04_completion_reopen.py:160: in test_CR4_reopening_one_progress_segment_requires_segment_identity
    assert progress is not None, (
E   AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
E   assert None is not None
____ test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution ____
planning/tests/contract/test_04_completion_reopen.py:181: in test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it exists, completing B while prerequisite A is incomplete must require cancel OR explicit edge removal; ARC may not silently break A->B.
E   assert None is not None
_________ test_CR8_reopening_completed_prerequisite_requires_explicit_resolution __________
planning/tests/contract/test_04_completion_reopen.py:191: in test_CR8_reopening_completed_prerequisite_requires_explicit_resolution
    assert dependency is not None, (
E   AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopening prerequisite A while dependent B remains complete must require explicit conflict resolution rather than silently violating/removing A->B.
E   assert None is not None
__ test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child ___
planning/tests/contract/test_05_structural_frontier.py:153: in test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child
    assert field is not None, (
E   AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must exist before anchor suspension/inheritance can be implemented
E   assert None is not None
_________ test_H7_reversing_anchored_structural_transition_restores_parent_intent _________
planning/tests/contract/test_05_structural_frontier.py:182: in test_H7_reversing_anchored_structural_transition_restores_parent_intent
    assert field is not None, (
E   AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
E   assert None is not None
_______ test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent ________
planning/tests/contract/test_06_reparenting.py:154: in test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent
    assert dependency is not None, (
E   AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once present, reparenting an endpoint must preserve valid edges and reject/require explicit resolution for invalid semantics; it may never silently delete the dependency.
E   assert None is not None
_________________ test_D2_subtree_delete_requires_atomic_domain_semantics _________________
planning/tests/contract/test_07_delete_restore_undo.py:89: in test_D2_subtree_delete_requires_atomic_domain_semantics
    assert delete is not None, (
E   AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/subtree so active descendants/parent references cannot be left dangling by a partial multi-write operation
E   assert None is not None
___________ test_D3_deleting_dependency_endpoint_requires_edge_restore_history ____________
planning/tests/contract/test_07_delete_restore_undo.py:99: in test_D3_deleting_dependency_endpoint_requires_edge_restore_history
    assert dependency is not None, (
E   AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting an endpoint must suspend/remove incident active edges while retaining enough canonical/history context for safe restore.
E   assert None is not None
_____________ test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip _____________
planning/tests/contract/test_07_delete_restore_undo.py:109: in test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip
    assert restore is not None, (
E   AssertionError: D4 MISSING: restore must be a domain command that validates the original parent/dependency relationships against the current world; raw is_deleted=False is insufficient.
E   assert None is not None
_____________________ test_D5_restore_must_revalidate_hierarchy_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:118: in test_D5_restore_must_revalidate_hierarchy_cycle
    assert restore is not None, (
E   AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore must reject/redirect an original parent relationship that would now create a hierarchy cycle.
E   assert None is not None
____________________ test_D6_restore_must_revalidate_dependency_cycle _____________________
planning/tests/contract/test_07_delete_restore_undo.py:128: in test_D6_restore_must_revalidate_dependency_cycle
    assert restore is not None and dependency is not None, (
E   AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required. An old dependency edge may not be silently reactivated if it would create a dependency cycle in the present world.
E   assert (None is not None)
________ test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it _________
planning/tests/contract/test_07_delete_restore_undo.py:138: in test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it
    assert "manual_requested_date" in names, (
E   AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority ________
planning/tests/contract/test_09_dependencies.py:91: in test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_____________________ test_DP2_self_dependency_is_rejected_atomically _____________________
planning/tests/contract/test_09_dependencies.py:109: in test_DP2_self_dependency_is_rejected_atomically
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__________ test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges __________
planning/tests/contract/test_09_dependencies.py:125: in test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____________________ test_DP1_DP7_dependency_edits_are_tenant_isolated ____________________
planning/tests/contract/test_09_dependencies.py:143: in test_DP1_DP7_dependency_edits_are_tenant_isolated
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
________ test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier ________
planning/tests/contract/test_09_dependencies.py:155: in test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_________________ test_DP3_completing_prerequisite_may_unblock_dependant __________________
planning/tests/contract/test_09_dependencies.py:168: in test_DP3_completing_prerequisite_may_unblock_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
______________ test_DP4_reopening_prerequisite_reblocks_unfinished_dependant ______________
planning/tests/contract/test_09_dependencies.py:180: in test_DP4_reopening_prerequisite_reblocks_unfinished_dependant
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
_ test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete _
planning/tests/contract/test_09_dependencies.py:196: in test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete
    _, service = _require_dependency_layer()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
__ test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete __
planning/tests/contract/test_09_dependencies.py:215: in test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete
    model, service = _require_dependency_layer()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
____ test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold _____
planning/tests/contract/test_09_dependencies.py:236: in test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold
    model, _ = _require_dependency_layer()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_09_dependencies.py:56: in _require_dependency_layer
    assert model is not None and service is not None, (
E   AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain commands. A -> B means B cannot execute until A is complete.
E   assert (None is not None)
________ test_DP9_scheduler_cannot_place_dependant_before_incomplete_prerequisite _________
planning/tests/contract/test_09_dependencies.py:265: in test_DP9_scheduler_cannot_place_dependant_before_incomplete_prerequisite
    assert dependency_service is not None, (
E   AssertionError: DEP-009 prerequisite: canonical dependency service/graph
E   assert None is not None
______ test_TMP008_scheduler_avoids_deadline_day_when_safer_earlier_day_is_feasible _______
planning/tests/contract/test_10_temporal.py:336: in test_TMP008_scheduler_avoids_deadline_day_when_safer_earlier_day_is_feasible
    assert placed is not None
E   assert None is not None
______________ test_A1_valid_anchor_is_canonical_and_distinct_from_priority _______________
planning/tests/contract/test_11_anchors.py:84: in test_A1_valid_anchor_is_canonical_and_distinct_from_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
___________________ test_A2_moving_anchor_changes_canonical_anchor_date ___________________
planning/tests/contract/test_11_anchors.py:94: in test_A2_moving_anchor_changes_canonical_anchor_date
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__________ test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority ___________
planning/tests/contract/test_11_anchors.py:108: in test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority
    _set_anchor(item, today + timedelta(days=2))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change _____
planning/tests/contract/test_11_anchors.py:125: in test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change
    _set_anchor(item, due + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
__ test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change ___
planning/tests/contract/test_11_anchors.py:148: in test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change
    _set_anchor(item, today + timedelta(days=1))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
______________ test_A6_passing_anchor_date_does_not_itself_make_task_overdue ______________
planning/tests/contract/test_11_anchors.py:166: in test_A6_passing_anchor_date_does_not_itself_make_task_overdue
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:33: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____ test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace _____
planning/tests/contract/test_11_anchors.py:181: in test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace
    field = _anchor_field()
            ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:33: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
_____________ test_A9_automatic_missed_schedule_is_not_converted_into_anchor ______________
planning/tests/contract/test_11_anchors.py:234: in test_A9_automatic_missed_schedule_is_not_converted_into_anchor
    assert getattr(item, _anchor_field()) is None
                         ^^^^^^^^^^^^^^^
planning/tests/contract/test_11_anchors.py:33: in _anchor_field
    assert "manual_requested_date" in _fields(), (
E   AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
E    +  where {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...} = _fields()
__ test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor __
planning/tests/contract/test_11_anchors.py:242: in test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
_____________ test_A10_reversing_structural_episode_can_restore_parent_anchor _____________
planning/tests/contract/test_11_anchors.py:258: in test_A10_reversing_structural_episode_can_restore_parent_anchor
    _set_anchor(parent, today + timedelta(days=3))
planning/tests/contract/test_11_anchors.py:65: in _set_anchor
    return _call(
planning/tests/contract/test_11_anchors.py:59: in _call
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")
E   AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_manual_requested_date', 'request_date')
____ test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer _____
planning/tests/contract/test_11_anchors.py:276: in test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer
    assert any(callable(getattr(service, n, None)) for n in names), (
E   AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user-created infeasible or overloaded plans
E   assert False
E    +  where False = any(<generator object test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer.<locals>.<genexpr> at 0x10f460040>)
______ test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories _______
planning/tests/contract/test_12_duration_progress.py:108: in test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories
    assert EXPECTED_CLASSES <= values, (
E   AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >16h as distinct mutually-exclusive semantic classes. Current values: ['MIN_20_TO_60', 'OVER_60_MIN', 'UNDER_20_MIN']
E   assert {'OVER_16_HOU...NDER_8_HOURS'} <= {'MIN_20_TO_6...UNDER_20_MIN'}
E     
E     Extra items in the left set:
E     'UNDER_1_HOUR'
E     'UNDER_8_HOURS'
E     'UNDER_4_HOURS'
E     'OVER_16_HOURS'
E     'UNDER_20_MINUTES'
E     'UNDER_16_HOURS'
______ test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:132: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] ______
planning/tests/contract/test_12_duration_progress.py:132: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
______ test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] _______
planning/tests/contract/test_12_duration_progress.py:132: in test_E2_splittable_categories_have_canonical_percent_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_______ test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed ________
planning/tests/contract/test_12_duration_progress.py:143: in test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:93: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
____________ test_E3_splittable_to_atomic_discards_partial_progress_semantics _____________
planning/tests/contract/test_12_duration_progress.py:157: in test_E3_splittable_to_atomic_discards_partial_progress_semantics
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:93: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_________ test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress _________
planning/tests/contract/test_12_duration_progress.py:173: in test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress
    _set_progress(item, 45)
planning/tests/contract/test_12_duration_progress.py:93: in _set_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_____________ test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress _____________
planning/tests/contract/test_12_duration_progress.py:185: in test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress
    assert _get_progress(item) in (0, 0.0, None)
           ^^^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:100: in _get_progress
    return getattr(item, _progress_field())
                         ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_12_duration_progress.py:49: in _progress_field
    raise AssertionError(
E   AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress
_ test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal _
planning/tests/contract/test_12_duration_progress.py:218: in test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal
    assert model is not None, (
E   AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonical progress-segment/history identity so future scheduler proposals can change without rewriting confirmed progress
E   assert None is not None
________________ test_DUR009_reversing_one_completed_segment_can_be_local _________________
planning/tests/contract/test_12_duration_progress.py:229: in test_DUR009_reversing_one_completed_segment_can_be_local
    assert model is not None and service is not None, (
E   AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress service
E   assert (None is not None)
_____ test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations _____
planning/tests/contract/test_12_duration_progress.py:251: in test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations
    assert any(callable(getattr(service, n, None)) for n in complete_names)
E   assert False
E    +  where False = any(<generator object test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations.<locals>.<genexpr> at 0x10f462e40>)
___________ test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children ___________
planning/tests/contract/test_12_duration_progress.py:258: in test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children
    assert model is not None, "DUR-011 MISSING PREREQUISITE: progress segment model"
E   AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
E   assert None is not None
______ test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work ______
planning/tests/contract/test_13_large_allocations.py:99: in test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work
    assert model is not None, "ALLOC-001 MISSING: allocation/progress segment model"
E   AssertionError: ALLOC-001 MISSING: allocation/progress segment model
E   assert None is not None
______ test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress ______
planning/tests/contract/test_13_large_allocations.py:113: in test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:57: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______ test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress _______
planning/tests/contract/test_13_large_allocations.py:130: in test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress
    assert model is not None and service is not None
E   assert (None is not None)
_______________ test_L4_commenced_task_only_allocates_remaining_percentage ________________
planning/tests/contract/test_13_large_allocations.py:152: in test_L4_commenced_task_only_allocates_remaining_percentage
    assert model is not None
E   assert None is not None
____________ test_L5_reopening_one_completed_segment_reduces_only_its_progress ____________
planning/tests/contract/test_13_large_allocations.py:168: in test_L5_reopening_one_completed_segment_reduces_only_its_progress
    assert model is not None and service is not None
E   assert (None is not None)
_________________ test_L6_one_hundred_percent_reconciles_task_to_complete _________________
planning/tests/contract/test_13_large_allocations.py:183: in test_L6_one_hundred_percent_reconciles_task_to_complete
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:57: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
____________ test_L7_semantic_decomposition_does_not_fabricate_child_progress _____________
planning/tests/contract/test_13_large_allocations.py:205: in test_L7_semantic_decomposition_does_not_fabricate_child_progress
    field = _progress_field()
            ^^^^^^^^^^^^^^^^^
planning/tests/contract/test_13_large_allocations.py:57: in _progress_field
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")
E   AssertionError: ALLOC MISSING: canonical percent-completed field
_______________ test_L8_allocation_projection_is_not_semantic_planning_item _______________
planning/tests/contract/test_13_large_allocations.py:219: in test_L8_allocation_projection_is_not_semantic_planning_item
    assert model is not None
E   assert None is not None
_________________________ test_F1_focus_projection_service_exists _________________________
planning/tests/contract/test_14_focus.py:59: in test_F1_focus_projection_service_exists
    assert service is not None, "FOC-001 MISSING: Focus projection/service"
E   AssertionError: FOC-001 MISSING: Focus projection/service
E   assert None is not None
__________ test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket __________
planning/tests/contract/test_14_focus.py:66: in test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket
    assert service is not None
E   assert None is not None
_________________ test_F2_lookahead_is_read_only_and_does_not_reschedule __________________
planning/tests/contract/test_14_focus.py:76: in test_F2_lookahead_is_read_only_and_does_not_reschedule
    assert service is not None
E   assert None is not None
_________________ test_F3_F4_selecting_current_focus_is_convenience_only __________________
planning/tests/contract/test_14_focus.py:103: in test_F3_F4_selecting_current_focus_is_convenience_only
    assert service is not None
E   assert None is not None
__________________ test_F5_do_today_translates_to_explicit_today_anchor ___________________
planning/tests/contract/test_14_focus.py:124: in test_F5_do_today_translates_to_explicit_today_anchor
    assert service is not None
E   assert None is not None
__________ test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent __________
planning/tests/contract/test_14_focus.py:144: in test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent
    assert service is not None
E   assert None is not None
____________ test_F7_explicit_focus_reprioritise_uses_global_priority_service _____________
planning/tests/contract/test_14_focus.py:164: in test_F7_explicit_focus_reprioritise_uses_global_priority_service
    assert service is not None
E   assert None is not None
___________________ test_F8_wrong_visual_bucket_cannot_mutate_duration ____________________
planning/tests/contract/test_14_focus.py:177: in test_F8_wrong_visual_bucket_cannot_mutate_duration
    assert service is not None
E   assert None is not None
________ test_F9_non_executable_current_focus_is_cleared_without_planning_mutation ________
planning/tests/contract/test_14_focus.py:187: in test_F9_non_executable_current_focus_is_cleared_without_planning_mutation
    assert service is not None
E   assert None is not None
______ test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections _______
planning/tests/contract/test_17_view_coherence.py:127: in test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections
    move(*args)
/opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:85: in inner
    return func(*args, **kwds)
           ^^^^^^^^^^^^^^^^^^^
planning/services/priority.py:225: in reorder
    raise ValidationError('That task is not in the priority order.')
E   django.core.exceptions.ValidationError: ['That task is not in the priority order.']
____________ test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop _____________
planning/tests/contract/test_17_view_coherence.py:146: in test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop
    assert "manual_requested_date" in fields, (
E   AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
____________ test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning _____________
planning/tests/contract/test_17_view_coherence.py:197: in test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning
    assert service is not None, "VIEW-003 prerequisite: Focus projection"
E   AssertionError: VIEW-003 prerequisite: Focus projection
E   assert None is not None
___________ test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts ____________
planning/tests/contract/test_17_view_coherence.py:239: in test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts
    assert service is not None
E   assert None is not None
___________ test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes ____________
planning/tests/contract/test_17_view_coherence.py:268: in test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes
    assert commands is not None, (
E   AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boundary rather than separate serializer/view databases
E   assert None is not None
___________________ test_AUTH_001_hard_anchor_survives_scheduler_rerun ____________________
planning/tests/contract/test_18_scheduler_authority.py:87: in test_AUTH_001_hard_anchor_survives_scheduler_rerun
    assert "manual_requested_date" in fields, (
E   AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
_______________ test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts _______________
planning/tests/contract/test_18_scheduler_authority.py:122: in test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts
    assert _canonical(item) == before, (
E   AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may not
E   assert {'title': 'Ca...': False, ...} == {'title': 'Ca...': False, ...}
E     
E     Omitting 8 identical items, use -vv to show
E     Differing items:
E     {'priority_position': 1} != {'priority_position': None}
E     Use -v to get more diff
____________ test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges _____________
planning/tests/contract/test_18_scheduler_authority.py:131: in test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges
    assert dependency is not None, (
E   AssertionError: AUTH-002 prerequisite: dependency graph implementation
E   assert None is not None
____________ test_RT_001_delete_restore_round_trip_preserves_semantic_identity ____________
planning/tests/contract/test_19_round_trip.py:81: in test_RT_001_delete_restore_round_trip_preserves_semantic_identity
    assert delete is not None and restore is not None, (
E   AssertionError: RT-001 prerequisite: validated delete + restore domain commands
E   assert (None is not None)
____________ test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts ____________
planning/tests/contract/test_19_round_trip.py:169: in test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts
    assert "manual_requested_date" in fields, (
E   AssertionError: RT-004 prerequisite: canonical manual_requested_date
E   assert 'manual_requested_date' in {'assignment_detail', 'canvas_object_id', 'canvas_object_type', 'children', 'created_at', 'description', ...}
________ test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit _________
planning/tests/contract/test_16_transactions.py:54: in test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit
    assert commands is not None, (
E   AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather than independent serializer/model writes
E   assert None is not None
_________________ test_X1_failed_multi_field_edit_rolls_back_every_field __________________
planning/tests/contract/test_16_transactions.py:67: in test_X1_failed_multi_field_edit_rolls_back_every_field
    assert commands is not None
E   assert None is not None
___________ test_X3_risky_overload_needs_confirmation_capability_before_commit ____________
planning/tests/contract/test_16_transactions.py:100: in test_X3_risky_overload_needs_confirmation_capability_before_commit
    assert commands is not None
E   assert None is not None
________ test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised _________
planning/tests/contract/test_16_transactions.py:109: in test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised
    assert commands is not None
E   assert None is not None
================================= short test summary info =================================
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_existing_canonical_state_is_persisted[manual date intent / anchor-candidates1] - AssertionError: Frozen ARC contract requires canonical 'manual date intent / anchor' s...
FAILED planning/tests/contract/test_01_canonical_state.py::test_required_new_canonical_state_exists[confirmed splittable progress-candidates0] - AssertionError: MISSING CONTRACT IMPLEMENTATION: confirmed splittable progress. Expect...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduled_date_and_anchor_are_distinct_fields - AssertionError: assert 'manual_requested_date' in {'assignment_detail', 'canvas_object...
FAILED planning/tests/contract/test_01_canonical_state.py::test_scheduler_date_can_change_without_destroying_anchor - Failed: MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent
FAILED planning/tests/contract/test_03_creation.py::test_C2_child_creation_defaults_release_and_deadline_from_parent - AssertionError: C2 MISSING: child creation must default release/start_date from parent
FAILED planning/tests/contract/test_03_creation.py::test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it - Failed: C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_03_creation.py::test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion - AssertionError: C5 MISSING: a completed parent cannot remain semantically completed af...
FAILED planning/tests/contract/test_03_creation.py::test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress - Failed: C6 MISSING PREREQUISITE: no canonical percent-completed field for splittable t...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR1_complete_atomic_leaf_leaves_active_frontier - assert None is not None
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_CR6_splittable_completion_has_canonical_progress_state - AssertionError: CR3-CR6 MISSING: ARC needs canonical %completed plus reversible comple...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed - AssertionError: CR3 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR4_reopening_one_progress_segment_requires_segment_identity - AssertionError: CR4 MISSING PREREQUISITE: canonical splittable progress not implemented
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution - AssertionError: CR7 MISSING PREREQUISITE: dependency graph is not implemented. When it...
FAILED planning/tests/contract/test_04_completion_reopen.py::test_CR8_reopening_completed_prerequisite_requires_explicit_resolution - AssertionError: CR8 MISSING PREREQUISITE: dependency graph is not implemented. Reopeni...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child - AssertionError: H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor must e...
FAILED planning/tests/contract/test_05_structural_frontier.py::test_H7_reversing_anchored_structural_transition_restores_parent_intent - AssertionError: H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor
FAILED planning/tests/contract/test_06_reparenting.py::test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent - AssertionError: RP3 MISSING PREREQUISITE: dependency graph is not implemented. Once pr...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D2_subtree_delete_requires_atomic_domain_semantics - AssertionError: D2 MISSING: ARC needs one atomic domain command for deleting a parent/...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D3_deleting_dependency_endpoint_requires_edge_restore_history - AssertionError: D3 MISSING PREREQUISITE: dependency graph is not implemented. Deleting...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip - AssertionError: D4 MISSING: restore must be a domain command that validates the origin...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D5_restore_must_revalidate_hierarchy_cycle - AssertionError: D5 MISSING PREREQUISITE: no validated restore command exists. Restore ...
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D6_restore_must_revalidate_dependency_cycle - AssertionError: D6 MISSING PREREQUISITE: safe restore + dependency graph are required....
FAILED planning/tests/contract/test_07_delete_restore_undo.py::test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it - AssertionError: D7 MISSING PREREQUISITE: canonical anchor/manual date intent
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP2_self_dependency_is_rejected_atomically - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP1_DP7_dependency_edits_are_tenant_isolated - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP3_completing_prerequisite_may_unblock_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP4_reopening_prerequisite_reblocks_unfinished_dependant - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold - AssertionError: DEP MISSING: ARC needs a canonical dependency graph plus domain comman...
FAILED planning/tests/contract/test_09_dependencies.py::test_DP9_scheduler_cannot_place_dependant_before_incomplete_prerequisite - AssertionError: DEP-009 prerequisite: canonical dependency service/graph
FAILED planning/tests/contract/test_10_temporal.py::test_TMP008_scheduler_avoids_deadline_day_when_safer_earlier_day_is_feasible - assert None is not None
FAILED planning/tests/contract/test_11_anchors.py::test_A1_valid_anchor_is_canonical_and_distinct_from_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A2_moving_anchor_changes_canonical_anchor_date - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A6_passing_anchor_date_does_not_itself_make_task_overdue - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_automatic_missed_schedule_is_not_converted_into_anchor - AssertionError: ANC MISSING: canonical manual_requested_date/anchor field
FAILED planning/tests/contract/test_11_anchors.py::test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A10_reversing_structural_episode_can_restore_parent_anchor - AssertionError: ANC MISSING: no domain command among ('set_anchor', 'anchor', 'set_man...
FAILED planning/tests/contract/test_11_anchors.py::test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer - AssertionError: A11/A12: anchor mutation needs a validation/confirmation path for user...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories - AssertionError: DUR-001: duration model must represent <20m, <1h, <4h, <8h, <16h and >...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[OVER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_16_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_categories_have_canonical_percent_progress[UNDER_8_HOURS] - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E3_splittable_to_atomic_discards_partial_progress_semantics - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress - AssertionError: DUR-005 MISSING: splittable PlanningItem needs canonical percent-compl...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal - AssertionError: DUR-008 MISSING: completed allocation percentages need durable canonic...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR009_reversing_one_completed_segment_can_be_local - AssertionError: DUR-009 MISSING PREREQUISITE: durable progress segments + progress ser...
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations - assert False
FAILED planning/tests/contract/test_12_duration_progress.py::test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children - AssertionError: DUR-011 MISSING PREREQUISITE: progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work - AssertionError: ALLOC-001 MISSING: allocation/progress segment model
FAILED planning/tests/contract/test_13_large_allocations.py::test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L4_commenced_task_only_allocates_remaining_percentage - assert None is not None
FAILED planning/tests/contract/test_13_large_allocations.py::test_L5_reopening_one_completed_segment_reduces_only_its_progress - assert (None is not None)
FAILED planning/tests/contract/test_13_large_allocations.py::test_L6_one_hundred_percent_reconciles_task_to_complete - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L7_semantic_decomposition_does_not_fabricate_child_progress - AssertionError: ALLOC MISSING: canonical percent-completed field
FAILED planning/tests/contract/test_13_large_allocations.py::test_L8_allocation_projection_is_not_semantic_planning_item - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_projection_service_exists - AssertionError: FOC-001 MISSING: Focus projection/service
FAILED planning/tests/contract/test_14_focus.py::test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F2_lookahead_is_read_only_and_does_not_reschedule - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F3_F4_selecting_current_focus_is_convenience_only - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F5_do_today_translates_to_explicit_today_anchor - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F7_explicit_focus_reprioritise_uses_global_priority_service - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F8_wrong_visual_bucket_cannot_mutate_duration - assert None is not None
FAILED planning/tests/contract/test_14_focus.py::test_F9_non_executable_current_focus_is_cleared_without_planning_mutation - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections - django.core.exceptions.ValidationError: ['That task is not in the priority order.']
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop - AssertionError: VIEW-002 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning - AssertionError: VIEW-003 prerequisite: Focus projection
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts - assert None is not None
FAILED planning/tests/contract/test_17_view_coherence.py::test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes - AssertionError: VIEW-001/002: view-originated writes need a shared domain-command boun...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_001_hard_anchor_survives_scheduler_rerun - AssertionError: AUTH-001 prerequisite: canonical anchor/manual date intent
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts - AssertionError: AUTH-002: scheduler output may change, canonical user/domain facts may...
FAILED planning/tests/contract/test_18_scheduler_authority.py::test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges - AssertionError: AUTH-002 prerequisite: dependency graph implementation
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_001_delete_restore_round_trip_preserves_semantic_identity - AssertionError: RT-001 prerequisite: validated delete + restore domain commands
FAILED planning/tests/contract/test_19_round_trip.py::test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts - AssertionError: RT-004 prerequisite: canonical manual_requested_date
FAILED planning/tests/contract/test_16_transactions.py::test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit - AssertionError: TXN-001 MISSING: compound edits need a domain-command boundary rather ...
FAILED planning/tests/contract/test_16_transactions.py::test_X1_failed_multi_field_edit_rolls_back_every_field - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X3_risky_overload_needs_confirmation_capability_before_commit - assert None is not None
FAILED planning/tests/contract/test_16_transactions.py::test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised - assert None is not None
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % tree
.
├── __pycache__
│   ├── conftest.cpython-312-pytest-8.3.3.pyc
│   └── conftest.cpython-314-pytest-9.1.1.pyc
├── accounts
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── admin.cpython-314.pyc
│   │   ├── apps.cpython-314.pyc
│   │   ├── authentication.cpython-314.pyc
│   │   ├── models.cpython-314.pyc
│   │   ├── serializers.cpython-314.pyc
│   │   ├── tokens.cpython-314.pyc
│   │   ├── totp.cpython-314.pyc
│   │   ├── urls.cpython-314.pyc
│   │   └── views.cpython-314.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── authentication.py
│   ├── migrations
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── 0001_initial.cpython-314.pyc
│   │   └── 0001_initial.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   └── test_auth.cpython-314-pytest-9.1.1.pyc
│   │   ├── conftest.py
│   │   └── test_auth.py
│   ├── tokens.py
│   ├── totp.py
│   ├── urls.py
│   └── views.py
├── analytics
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── admin.cpython-314.pyc
│   │   ├── apps.cpython-314.pyc
│   │   ├── models.cpython-314.pyc
│   │   ├── serializers.cpython-314.pyc
│   │   ├── urls.cpython-314.pyc
│   │   └── views.cpython-314.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── migrations
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       └── __init__.cpython-314.pyc
│   ├── models.py
│   ├── serializers.py
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── test_api.cpython-314-pytest-9.1.1.pyc
│   │   └── test_api.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── arc_backend
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── settings.cpython-314.pyc
│   │   └── urls.cpython-314.pyc
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── arena.sqlite3
├── canvas_integration
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── admin.cpython-314.pyc
│   │   ├── apps.cpython-314.pyc
│   │   ├── client.cpython-314.pyc
│   │   ├── models.cpython-314.pyc
│   │   ├── serializers.cpython-314.pyc
│   │   ├── sync.cpython-314.pyc
│   │   ├── urls.cpython-314.pyc
│   │   └── views.cpython-314.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── client.py
│   ├── migrations
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── 0001_initial.cpython-314.pyc
│   │   └── 0001_initial.py
│   ├── models.py
│   ├── serializers.py
│   ├── sync.py
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   └── test_api.cpython-314-pytest-9.1.1.pyc
│   │   └── test_api.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── conftest.py
├── core
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── admin.cpython-314.pyc
│   │   ├── apps.cpython-314.pyc
│   │   ├── exceptions.cpython-314.pyc
│   │   ├── fields.cpython-314.pyc
│   │   ├── mixins.cpython-314.pyc
│   │   ├── models.cpython-314.pyc
│   │   ├── pagination.cpython-314.pyc
│   │   ├── permissions.cpython-314.pyc
│   │   ├── schema.cpython-314.pyc
│   │   └── serializers.cpython-314.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── exceptions.py
│   ├── fields.py
│   ├── management
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   └── __init__.cpython-314.pyc
│   │   └── commands
│   │       ├── __init__.py
│   │       └── seed_demo.py
│   ├── migrations
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       └── __init__.cpython-314.pyc
│   ├── mixins.py
│   ├── models.py
│   ├── pagination.py
│   ├── permissions.py
│   ├── schema.py
│   ├── serializers.py
│   ├── tests.py
│   └── views.py
├── manage.py
├── planning
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-314.pyc
│   │   ├── admin.cpython-314.pyc
│   │   ├── apps.cpython-314.pyc
│   │   ├── models.cpython-314.pyc
│   │   ├── queries.cpython-314.pyc
│   │   ├── serializers.cpython-314.pyc
│   │   ├── urls.cpython-314.pyc
│   │   └── views.cpython-314.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── migrations
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── 0001_initial.cpython-314.pyc
│   │   │   ├── 0002_planninghistoryentry.cpython-314.pyc
│   │   │   ├── 0003_planningitem_is_deleted.cpython-314.pyc
│   │   │   ├── 0004_planningitem_priority_restore_context_and_more.cpython-314.pyc
│   │   │   ├── 0005_scheduling_state.cpython-314.pyc
│   │   │   └── 0006_planningitem_manual_requested_date.cpython-314.pyc
│   │   ├── 0001_initial.py
│   │   ├── 0002_planninghistoryentry.py
│   │   ├── 0003_planningitem_is_deleted.py
│   │   ├── 0004_planningitem_priority_restore_context_and_more.py
│   │   └── 0005_scheduling_state.py
│   ├── models.py
│   ├── queries.py
│   ├── serializers.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── hierarchy.cpython-314.pyc
│   │   │   ├── history.cpython-314.pyc
│   │   │   ├── leaf_order_sync.cpython-314.pyc
│   │   │   ├── overdue.cpython-314.pyc
│   │   │   ├── priority.cpython-314.pyc
│   │   │   └── scheduling.cpython-314.pyc
│   │   ├── hierarchy.py
│   │   ├── history.py
│   │   ├── leaf_order_sync.py
│   │   ├── overdue.py
│   │   ├── priority.py
│   │   └── scheduling.py
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-314.pyc
│   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_api.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_hierarchy.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_history.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_independent_ordering.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_leaf_order_sync.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_overdue.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_priority_restoration.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_priority.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_scheduling_lifecycle.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_scheduling.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_state_semantics.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── test_tenant_isolation.cpython-314-pytest-9.1.1.pyc
│   │   │   └── test_timeline_scheduling.cpython-314-pytest-9.1.1.pyc
│   │   ├── conftest.py
│   │   ├── contract
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── conftest.cpython-314.pyc
│   │   │   │   ├── contract_manifest.cpython-314.pyc
│   │   │   │   ├── test_00_contract_coverage.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_00_contract_coverage.cpython-314.pyc
│   │   │   │   ├── test_01_canonical_state.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_01_canonical_state.cpython-314.pyc
│   │   │   │   ├── test_02_invariants.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_02_invariants.cpython-314.pyc
│   │   │   │   ├── test_03_creation.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_03_creation.cpython-314.pyc
│   │   │   │   ├── test_04_completion_reopen.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_04_completion_reopen.cpython-314.pyc
│   │   │   │   ├── test_05_structural_frontier.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_05_structural_frontier.cpython-314.pyc
│   │   │   │   ├── test_06_reparenting.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_06_reparenting.cpython-314.pyc
│   │   │   │   ├── test_07_delete_restore_undo.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_07_delete_restore_undo.cpython-314.pyc
│   │   │   │   ├── test_08_priority.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_08_priority.cpython-314.pyc
│   │   │   │   ├── test_09_dependencies.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_09_dependencies.cpython-314.pyc
│   │   │   │   ├── test_10_temporal.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_10_temporal.cpython-314.pyc
│   │   │   │   ├── test_11_anchors.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_11_anchors.cpython-314.pyc
│   │   │   │   ├── test_12_duration_progress.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_12_duration_progress.cpython-314.pyc
│   │   │   │   ├── test_13_large_allocations.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_13_large_allocations.cpython-314.pyc
│   │   │   │   ├── test_14_focus.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_14_focus.cpython-314.pyc
│   │   │   │   ├── test_15_scheduler_timeline.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_15_scheduler_timeline.cpython-314.pyc
│   │   │   │   ├── test_16_transactions.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_16_transactions.cpython-314.pyc
│   │   │   │   ├── test_17_view_coherence.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_17_view_coherence.cpython-314.pyc
│   │   │   │   ├── test_18_scheduler_authority.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_18_scheduler_authority.cpython-314.pyc
│   │   │   │   ├── test_19_round_trip.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_19_round_trip.cpython-314.pyc
│   │   │   │   ├── test_20_state_machine_torture.cpython-314-pytest-9.1.1.pyc
│   │   │   │   └── test_20_state_machine_torture.cpython-314.pyc
│   │   │   ├── conftest.py
│   │   │   ├── contract_manifest.py
│   │   │   ├── test_00_contract_coverage.py
│   │   │   ├── test_01_canonical_state.py
│   │   │   ├── test_02_invariants.py
│   │   │   ├── test_03_creation.py
│   │   │   ├── test_04_completion_reopen.py
│   │   │   ├── test_05_structural_frontier.py
│   │   │   ├── test_06_reparenting.py
│   │   │   ├── test_07_delete_restore_undo.py
│   │   │   ├── test_08_priority.py
│   │   │   ├── test_09_dependencies.py
│   │   │   ├── test_10_temporal.py
│   │   │   ├── test_11_anchors.py
│   │   │   ├── test_12_duration_progress.py
│   │   │   ├── test_13_large_allocations.py
│   │   │   ├── test_14_focus.py
│   │   │   ├── test_15_scheduler_timeline.py
│   │   │   ├── test_16_transactions.py
│   │   │   ├── test_17_view_coherence.py
│   │   │   ├── test_18_scheduler_authority.py
│   │   │   ├── test_19_round_trip.py
│   │   │   ├── test_20_state_machine_torture.py
│   │   │   └── tests.zip
│   │   ├── contract.backup
│   │   │   ├── __init__.py
│   │   │   ├── __pycache__
│   │   │   │   ├── __init__.cpython-314.pyc
│   │   │   │   ├── conftest.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── contract_manifest.cpython-314.pyc
│   │   │   │   ├── test_00_contract_coverage.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_01_canonical_state.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_02_invariants.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_03_creation.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_04_completion_reopen.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_05_structural_frontier.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_06_reparenting.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_07_delete_restore_undo.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_08_priority.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_09_dependencies.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_10_temporal.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_11_anchors.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_12_duration_progress.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_13_large_allocations.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_14_focus.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_15_scheduler_timeline.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_16_transactions.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_17_view_coherence.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_18_scheduler_authority.cpython-314-pytest-9.1.1.pyc
│   │   │   │   ├── test_19_round_trip.cpython-314-pytest-9.1.1.pyc
│   │   │   │   └── test_20_state_machine_torture.cpython-314-pytest-9.1.1.pyc
│   │   │   ├── conftest.py
│   │   │   ├── contract_manifest.py
│   │   │   ├── test_00_contract_coverage.py
│   │   │   ├── test_01_canonical_state.py
│   │   │   ├── test_02_invariants.py
│   │   │   ├── test_03_creation.py
│   │   │   ├── test_04_completion_reopen.py
│   │   │   ├── test_05_structural_frontier.py
│   │   │   ├── test_06_reparenting.py
│   │   │   ├── test_07_delete_restore_undo.py
│   │   │   ├── test_08_priority.py
│   │   │   ├── test_09_dependencies.py
│   │   │   ├── test_10_temporal.py
│   │   │   ├── test_11_anchors.py
│   │   │   ├── test_12_duration_progress.py
│   │   │   ├── test_13_large_allocations.py
│   │   │   ├── test_14_focus.py
│   │   │   ├── test_15_scheduler_timeline.py
│   │   │   ├── test_16_transactions.py
│   │   │   ├── test_17_view_coherence.py
│   │   │   ├── test_18_scheduler_authority.py
│   │   │   ├── test_19_round_trip.py
│   │   │   ├── test_20_state_machine_torture.py
│   │   │   └── tests.zip
│   │   ├── test_api.py
│   │   ├── test_hierarchy.py
│   │   ├── test_history.py
│   │   ├── test_independent_ordering.py
│   │   ├── test_leaf_order_sync.py
│   │   ├── test_overdue.py
│   │   ├── test_priority_restoration.py
│   │   ├── test_priority.py
│   │   ├── test_scheduling_lifecycle.py
│   │   ├── test_scheduling.py
│   │   ├── test_state_semantics.py
│   │   ├── test_tenant_isolation.py
│   │   └── test_timeline_scheduling.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── pytest.ini
├── requirements-lock.txt
└── requirements.txt

41 directories, 318 files
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % rm -f ~/Desktop/arc_cluster_01.zip

zip -r ~/Desktop/arc_cluster_01.zip \
  planning/models.py \
  planning/queries.py \
  planning/serializers.py \
  planning/views.py \
  planning/urls.py \
  planning/admin.py \
  planning/migrations \
  planning/services \
  planning/tests/contract \
  planning/tests/conftest.py \
  planning/tests/test_state_semantics.py \
  planning/tests/test_scheduling.py \
  planning/tests/test_scheduling_lifecycle.py \
  planning/tests/test_hierarchy.py \
  planning/tests/test_priority.py \
  planning/tests/test_priority_restoration.py \
  planning/tests/test_timeline_scheduling.py \
  ../docs/Arc \
  ../docs/scheduling_domain_contract.md \
  ../docs/user-intent-matrix.md \
  ../arc_backend_contract_audit.md \
  -x '*/__pycache__/*' '*.pyc' '*.zip' &&
echo "✅ Created ~/Desktop/arc_cluster_01.zip" &&
ls -lh ~/Desktop/arc_cluster_01.zip &&
osascript -e 'set the clipboard to POSIX file "'"$HOME"'/Desktop/arc_cluster_01.zip"'
  adding: planning/models.py (deflated 70%)
  adding: planning/queries.py (deflated 65%)
  adding: planning/serializers.py (deflated 75%)
  adding: planning/views.py (deflated 78%)
  adding: planning/urls.py (deflated 68%)
  adding: planning/admin.py (deflated 2%)
  adding: planning/migrations/ (stored 0%)
  adding: planning/migrations/0003_planningitem_is_deleted.py (deflated 41%)
  adding: planning/migrations/__init__.py (stored 0%)
  adding: planning/migrations/0004_planningitem_priority_restore_context_and_more.py (deflated 69%)
  adding: planning/migrations/0002_planninghistoryentry.py (deflated 56%)
  adding: planning/migrations/0005_scheduling_state.py (deflated 51%)
  adding: planning/migrations/0001_initial.py (deflated 80%)
  adding: planning/services/ (stored 0%)
  adding: planning/services/__init__.py (deflated 35%)
  adding: planning/services/priority.py (deflated 70%)
  adding: planning/services/hierarchy.py (deflated 63%)
  adding: planning/services/overdue.py (deflated 54%)
  adding: planning/services/scheduling.py (deflated 73%)
  adding: planning/services/leaf_order_sync.py (deflated 64%)
  adding: planning/services/history.py (deflated 75%)
  adding: planning/tests/contract/ (stored 0%)
  adding: planning/tests/contract/conftest.py (deflated 63%)
  adding: planning/tests/contract/.DS_Store (deflated 87%)
  adding: planning/tests/contract/test_11_anchors.py (deflated 72%)
  adding: planning/tests/contract/test_15_scheduler_timeline.py (deflated 69%)
  adding: planning/tests/contract/test_07_delete_restore_undo.py (deflated 66%)
  adding: planning/tests/contract/test_09_dependencies.py (deflated 75%)
  adding: planning/tests/contract/test_13_large_allocations.py (deflated 73%)
  adding: planning/tests/contract/test_06_reparenting.py (deflated 69%)
  adding: planning/tests/contract/test_19_round_trip.py (deflated 70%)
  adding: planning/tests/contract/test_20_state_machine_torture.py (deflated 70%)
  adding: planning/tests/contract/test_08_priority.py (deflated 72%)
  adding: planning/tests/contract/test_04_completion_reopen.py (deflated 72%)
  adding: planning/tests/contract/__init__.py (deflated 29%)
  adding: planning/tests/contract/test_01_canonical_state.py (deflated 67%)
  adding: planning/tests/contract/test_17_view_coherence.py (deflated 72%)
  adding: planning/tests/contract/test_00_contract_coverage.py (deflated 63%)
  adding: planning/tests/contract/contract_manifest.py (deflated 69%)
  adding: planning/tests/contract/test_16_transactions.py (deflated 66%)
  adding: planning/tests/contract/test_12_duration_progress.py (deflated 71%)
  adding: planning/tests/contract/test_02_invariants.py (deflated 73%)
  adding: planning/tests/contract/test_18_scheduler_authority.py (deflated 69%)
  adding: planning/tests/contract/test_10_temporal.py (deflated 74%)
  adding: planning/tests/contract/test_03_creation.py (deflated 71%)
  adding: planning/tests/contract/test_05_structural_frontier.py (deflated 74%)
  adding: planning/tests/contract/test_14_focus.py (deflated 71%)
  adding: planning/tests/conftest.py (deflated 57%)
  adding: planning/tests/test_state_semantics.py (deflated 84%)
  adding: planning/tests/test_scheduling.py (deflated 79%)
  adding: planning/tests/test_scheduling_lifecycle.py (deflated 80%)
  adding: planning/tests/test_hierarchy.py (deflated 76%)
  adding: planning/tests/test_priority.py (deflated 71%)
  adding: planning/tests/test_priority_restoration.py (deflated 77%)
  adding: planning/tests/test_timeline_scheduling.py (deflated 78%)
  adding: ../docs/Arc/ (stored 0%)
  adding: ../docs/Arc/algorithm_manages.md (deflated 54%)
  adding: ../docs/Arc/.DS_Store (deflated 87%)
  adding: ../docs/Arc/conflict_resolution.md (deflated 57%)
  adding: ../docs/Arc/general_rules.md (deflated 60%)
  adding: ../docs/Arc/invariants.md (deflated 60%)
  adding: ../docs/Arc/states.md (deflated 54%)
  adding: ../docs/Arc/arc_guaranteed.md (deflated 49%)
  adding: ../docs/Arc/what_each_of_these_files_contain.md (deflated 45%)
  adding: ../docs/Arc/state_transitions.md (deflated 67%)
  adding: ../docs/Arc/canonical_state.md (deflated 55%)
  adding: ../docs/Arc/domain_commands.md (deflated 53%)
  adding: ../docs/scheduling_domain_contract.md (stored 0%)
  adding: ../docs/user-intent-matrix.md (deflated 61%)
  adding: ../arc_backend_contract_audit.md (deflated 81%)
✅ Created ~/Desktop/arc_cluster_01.zip
-rw-r--r--@ 1 rajdipshah  staff   210K 20 Sep 23:04 /Users/rajdipshah/Desktop/arc_cluster_01.zip
(.venv) rajdipshah@Rajdips-MacBook-Air ~/UNI/Y3S1 - 2026 sem 2/ELEC3609/ARC-Scheduler-Arena/backend % >....                                                                           
                    models.BooleanField(default=False),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_segments",
                        to="planning.planningitem",
                    ),
                ),
            ],
            options={
                "db_table": "planning_progress_segments",
                "ordering": ["scheduled_date", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="progresssegment",
            constraint=models.CheckConstraint(
                condition=Q(percentage__gt=0) & Q(percentage__lte=100),
                name="progress_segment_percentage_range",
            ),
        ),

        # Convert existing three-category data before the application begins
        # using the frozen six-category vocabulary.
        migrations.RunPython(
            migrate_old_duration_categories,
            migrations.RunPython.noop,
        ),

        # Preserve legacy explicit manual placements as canonical anchor facts.
        migrations.RunPython(
            preserve_legacy_manual_dates,
            migrations.RunPython.noop,
        ),
    ]
PY

echo "✓ planning/migrations/0006_contract_foundations.py"

echo
echo "🔎 Checking Django model/migration consistency..."

python manage.py makemigrations --check --dry-run

echo
echo "🗄️ Applying migration..."

python manage.py migrate

echo
echo "<0001f9ea> Compiling changed Python..."

python -m compileall -q planning

echo
echo "✅ Cluster 1 implementation installed."
echo "📦 Backup remains at: $BACKUP"
📦 Backup: ../cluster01_backup_20260920_231501
✓ planning/models.py
✓ planning/serializers.py
✓ planning/services/scheduling.py
✓ planning/services/progress.py
✓ planning/services/dependencies.py
✓ planning/migrations/0006_contract_foundations.py

🔎 Checking Django model/migration consistency...
System check identified some issues:

WARNINGS:
planning.PlanningItem: (models.W038) SQLite does not support deferrable unique constraints.
	HINT: A constraint won't be created. Silence this warning if you don't care about it.
Migrations for 'planning':
  planning/migrations/0007_alter_planningdependency_id_alter_progresssegment_id.py
    ~ Alter field id on planningdependency
    ~ Alter field id on progresssegment

[Process completed]

here's a copy of the terminal trasncript , 

i am opening a new temrinal and make sure you don't cause this bullshit again
