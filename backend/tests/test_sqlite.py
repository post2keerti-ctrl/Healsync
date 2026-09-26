from pathlib import Path

from healsync_backend.contracts import UserRecord
from healsync_backend.db.repositories.users import SQLiteUserRepository
from healsync_backend.db.sqlite import SQLiteDatabase
from healsync_backend.doctor_routes import list_patients
from healsync_backend.seed import seed_sqlite


def test_sqlite_user_repository_preserves_role(tmp_path: Path) -> None:
    with SQLiteDatabase(tmp_path / "test.db") as database:
        database.initialize()
        repository = SQLiteUserRepository(database)
        user = repository.create_or_update(UserRecord("", "firebase-1", "person@example.com", "Person", "patient"))
        assert user.id
        assert repository.get_by_firebase_uid("firebase-1").role == "patient"

        try:
            repository.create_or_update(UserRecord(user.id, "firebase-1", "person@example.com", "Person", "doctor"))
        except ValueError as error:
            assert "role" in str(error)
        else:
            raise AssertionError("role changes must be rejected")


def test_seed_links_doctor_to_fully_recovered_patient(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with SQLiteDatabase() as database:
        database.initialize()
        seed_sqlite(database)
        rows = database.execute(
            """
                 SELECT doctor.name AS doctor_name, patient.name AS patient_name,
                     patient.id AS patient_user_id, profile.id AS patient_profile_id,
                   profile.recovery_day, profile.recovery_total_days, profile.confidence_score
            FROM patient_profiles profile
            JOIN users patient ON patient.id = profile.user_id
            JOIN doctor_profiles doctor_profile ON doctor_profile.id = profile.doctor_id
            JOIN users doctor ON doctor.id = doctor_profile.user_id
            """
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["doctor_name"] == "Dr. Meera Rao"
        assert rows[0]["patient_name"] == "Karthik Subramanian"
        assert rows[0]["recovery_day"] == rows[0]["recovery_total_days"] == 14
        assert rows[0]["confidence_score"] == 100
        patient_user_id = rows[0]["patient_user_id"]
        patient_profile_id = rows[0]["patient_profile_id"]
        doctor_id = database.execute("SELECT id FROM users WHERE email = 'doctor@healsync.com'").fetchone()[0]

        seed_sqlite(database)
        assert database.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3

    from healsync_backend.contracts import PatientProfile, UserRecord
    from healsync_backend.patient_routes import dashboard

    patients = list_patients(UserRecord(doctor_id, "dev:doctor@healsync.com", "doctor@healsync.com", "Dr. Meera Rao", "doctor"))
    assert len(patients) == 1
    assert patients[0]["name"] == "Karthik Subramanian"
    assert patients[0]["recovery_percent"] == 100
    assert patients[0]["fully_recovered"] is True
    patient_user = UserRecord(patient_user_id, "dev:karthik@healsync.com", "karthik@healsync.com", "Karthik Subramanian", "patient")
    patient_profile = PatientProfile(patient_profile_id, patient_user_id, "Knee surgery", 14, 14, 100, 13.0350, 80.2450)
    assert dashboard((patient_user, patient_profile))["doctor_name"] == "Dr. Meera Rao"
