-- Baseline schema for the PostgreSQL integration tests (tests/integration).
--
-- Schema-only snapshot of the application database as it was BEFORE migration 003
-- (timestamp columns are still `timestamp without time zone`), taken with
-- `pg_dump --schema-only --no-owner --no-acl`. Contains no data. The tests load it into a
-- throwaway database and then apply migrations/003 (and 004) on top, exactly as production does.
-- Regenerate it only if the pre-003 base schema itself changes.
--
-- PostgreSQL database dump
--


-- Dumped from database version 17.9
-- Dumped by pg_dump version 17.9

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: appointment_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appointment_status AS ENUM (
    'SCHEDULED',
    'CONFIRMED',
    'CANCELLED',
    'COMPLETED'
);


--
-- Name: gender_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.gender_type AS ENUM (
    'MALE',
    'FEMALE',
    'OTHER',
    'PREFER_NOT_TO_SAY'
);


--
-- Name: slot_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.slot_status AS ENUM (
    'AVAILABLE',
    'BOOKED',
    'BLOCKED'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'ADMIN',
    'DOCTOR',
    'PATIENT'
);


--
-- Name: audit_trigger_function(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.audit_trigger_function() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_user UUID;
    v_tenant UUID;
BEGIN

    BEGIN
        v_user := current_setting('app.current_user_id')::uuid;
    EXCEPTION WHEN OTHERS THEN
        v_user := NULL;
    END;

    BEGIN
        v_tenant := current_setting('app.current_tenant')::uuid;
    EXCEPTION WHEN OTHERS THEN
        v_tenant := NULL;
    END;

    IF TG_OP = 'INSERT' THEN

        INSERT INTO audit_logs (
            tenant_id, table_name, record_id,
            action_type, new_data, performed_by
        )
        VALUES (
            v_tenant,
            TG_TABLE_NAME,
            NEW.id,
            'INSERT',
            to_jsonb(NEW),
            v_user
        );

        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE' THEN

        INSERT INTO audit_logs (
            tenant_id, table_name, record_id,
            action_type, old_data, new_data, performed_by
        )
        VALUES (
            v_tenant,
            TG_TABLE_NAME,
            NEW.id,
            'UPDATE',
            to_jsonb(OLD),
            to_jsonb(NEW),
            v_user
        );

        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN

        INSERT INTO audit_logs (
            tenant_id, table_name, record_id,
            action_type, old_data, performed_by
        )
        VALUES (
            v_tenant,
            TG_TABLE_NAME,
            OLD.id,
            'DELETE',
            to_jsonb(OLD),
            v_user
        );

        RETURN OLD;
    END IF;

END;
$$;


--
-- Name: sync_doctor_availability(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sync_doctor_availability() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN

    -- INSERT → book slot
    IF TG_OP = 'INSERT' THEN
        UPDATE doctor_availability
        SET status = 'BOOKED'
        WHERE doctor_id = NEW.doctor_id
        AND slot_time = NEW.appointment_time;

        RETURN NEW;
    END IF;

    -- UPDATE
    IF TG_OP = 'UPDATE' THEN

        -- if appointment cancelled → free slot
        IF NEW.status = 'CANCELLED' THEN
            UPDATE doctor_availability
            SET status = 'AVAILABLE'
            WHERE doctor_id = NEW.doctor_id
            AND slot_time = NEW.appointment_time;
        END IF;

        RETURN NEW;

    END IF;

    -- DELETE → free slot
    IF TG_OP = 'DELETE' THEN
        UPDATE doctor_availability
        SET status = 'AVAILABLE'
        WHERE doctor_id = OLD.doctor_id
        AND slot_time = OLD.appointment_time;

        RETURN OLD;
    END IF;

    RETURN NULL;

END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admins (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid,
    full_name character varying(255),
    phone character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid
);


--
-- Name: appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointments (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    doctor_id uuid NOT NULL,
    patient_id uuid NOT NULL,
    appointment_time timestamp without time zone NOT NULL,
    status public.appointment_status DEFAULT 'SCHEDULED'::public.appointment_status,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid,
    slot_id uuid
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid,
    table_name text NOT NULL,
    record_id uuid NOT NULL,
    action_type text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    performed_by uuid,
    performed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: doctor_availability; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doctor_availability (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    doctor_id uuid NOT NULL,
    slot_time timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    status public.slot_status DEFAULT 'AVAILABLE'::public.slot_status,
    block_reason text
);


--
-- Name: doctors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doctors (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    full_name character varying(255) NOT NULL,
    specialty character varying(255),
    license_number character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid,
    phone character varying(20),
    date_of_birth date
);


--
-- Name: medical_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medical_records (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    appointment_id uuid NOT NULL,
    symptoms text,
    diagnosis text,
    lab_results text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid
);


--
-- Name: patient_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_documents (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    patient_id uuid NOT NULL,
    document_name character varying(255),
    document_type character varying(100),
    file_path text,
    signed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid
);


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    full_name character varying(255) NOT NULL,
    phone character varying(50),
    insurance_provider character varying(255),
    insurance_policy_number character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid,
    date_of_birth date,
    gender character varying(20),
    address_line1 character varying(255),
    address_line2 character varying(255),
    city character varying(100),
    state character varying(100),
    postal_code character varying(20),
    country character varying(100)
);


--
-- Name: pharmacies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pharmacies (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid,
    address text,
    phone text
);


--
-- Name: prescriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prescriptions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    medical_record_id uuid NOT NULL,
    pharmacy_id uuid,
    medication_details text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(255) NOT NULL,
    domain character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash text NOT NULL,
    role public.user_role NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamp without time zone,
    deleted_by uuid
);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (id);


--
-- Name: admins admins_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_user_id_key UNIQUE (user_id);


--
-- Name: appointments appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: doctor_availability doctor_availability_doctor_id_slot_time_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_availability
    ADD CONSTRAINT doctor_availability_doctor_id_slot_time_key UNIQUE (doctor_id, slot_time);


--
-- Name: doctor_availability doctor_availability_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_availability
    ADD CONSTRAINT doctor_availability_pkey PRIMARY KEY (id);


--
-- Name: doctors doctors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_pkey PRIMARY KEY (id);


--
-- Name: doctors doctors_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_user_id_key UNIQUE (user_id);


--
-- Name: medical_records medical_records_appointment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_appointment_id_key UNIQUE (appointment_id);


--
-- Name: medical_records medical_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_pkey PRIMARY KEY (id);


--
-- Name: patient_documents patient_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_documents
    ADD CONSTRAINT patient_documents_pkey PRIMARY KEY (id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: patients patients_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_user_id_key UNIQUE (user_id);


--
-- Name: pharmacies pharmacies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacies
    ADD CONSTRAINT pharmacies_pkey PRIMARY KEY (id);


--
-- Name: prescriptions prescriptions_medical_record_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_medical_record_id_key UNIQUE (medical_record_id);


--
-- Name: prescriptions prescriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_domain_key UNIQUE (domain);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: admins unique_admin_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT unique_admin_user UNIQUE (user_id);


--
-- Name: doctor_availability unique_slot_tenant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_availability
    ADD CONSTRAINT unique_slot_tenant UNIQUE (id, tenant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_tenant_id_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_email_key UNIQUE (tenant_id, email);


--
-- Name: idx_admins_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admins_tenant ON public.admins USING btree (tenant_id);


--
-- Name: idx_appointments_doctor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_doctor ON public.appointments USING btree (doctor_id);


--
-- Name: idx_appointments_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_patient ON public.appointments USING btree (patient_id);


--
-- Name: idx_appointments_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_time ON public.appointments USING btree (appointment_time);


--
-- Name: idx_availability_doctor_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_doctor_time ON public.doctor_availability USING btree (doctor_id, slot_time);


--
-- Name: idx_doctors_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doctors_tenant ON public.doctors USING btree (tenant_id);


--
-- Name: idx_medical_records_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_medical_records_tenant ON public.medical_records USING btree (tenant_id);


--
-- Name: idx_patients_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_patients_tenant ON public.patients USING btree (tenant_id);


--
-- Name: idx_prescriptions_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prescriptions_tenant ON public.prescriptions USING btree (tenant_id);


--
-- Name: idx_users_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_tenant ON public.users USING btree (tenant_id);


--
-- Name: unique_doctor_time; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX unique_doctor_time ON public.appointments USING btree (doctor_id, appointment_time) WHERE (status <> 'CANCELLED'::public.appointment_status);


--
-- Name: unique_patient_time; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX unique_patient_time ON public.appointments USING btree (patient_id, appointment_time) WHERE (status <> 'CANCELLED'::public.appointment_status);


--
-- Name: appointments audit_appointments; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_appointments AFTER INSERT OR DELETE OR UPDATE ON public.appointments FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: doctors audit_doctors; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_doctors AFTER INSERT OR DELETE OR UPDATE ON public.doctors FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: patient_documents audit_documents; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_documents AFTER INSERT OR DELETE OR UPDATE ON public.patient_documents FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: medical_records audit_medical_records; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_medical_records AFTER INSERT OR DELETE OR UPDATE ON public.medical_records FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: patients audit_patients; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_patients AFTER INSERT OR DELETE OR UPDATE ON public.patients FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: pharmacies audit_pharmacies; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_pharmacies AFTER INSERT OR DELETE OR UPDATE ON public.pharmacies FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: prescriptions audit_prescriptions; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_prescriptions AFTER INSERT OR DELETE OR UPDATE ON public.prescriptions FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: users audit_users; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_users AFTER INSERT OR DELETE OR UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();


--
-- Name: appointments trg_sync_availability; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_sync_availability AFTER INSERT OR DELETE OR UPDATE ON public.appointments FOR EACH ROW EXECUTE FUNCTION public.sync_doctor_availability();


--
-- Name: admins admins_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: admins admins_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: appointments appointments_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id) ON DELETE CASCADE;


--
-- Name: appointments appointments_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;


--
-- Name: appointments appointments_slot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_slot_id_fkey FOREIGN KEY (slot_id) REFERENCES public.doctor_availability(id) ON DELETE CASCADE;


--
-- Name: appointments appointments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: doctor_availability doctor_availability_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_availability
    ADD CONSTRAINT doctor_availability_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id) ON DELETE CASCADE;


--
-- Name: doctor_availability doctor_availability_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_availability
    ADD CONSTRAINT doctor_availability_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: doctors doctors_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: doctors doctors_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: admins fk_admin_deleted_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT fk_admin_deleted_by FOREIGN KEY (deleted_by) REFERENCES public.users(id);


--
-- Name: appointments fk_slot_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT fk_slot_tenant FOREIGN KEY (slot_id, tenant_id) REFERENCES public.doctor_availability(id, tenant_id) ON DELETE CASCADE;


--
-- Name: medical_records medical_records_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES public.appointments(id) ON DELETE CASCADE;


--
-- Name: medical_records medical_records_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: patient_documents patient_documents_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_documents
    ADD CONSTRAINT patient_documents_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;


--
-- Name: patient_documents patient_documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_documents
    ADD CONSTRAINT patient_documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: patients patients_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: patients patients_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: pharmacies pharmacies_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacies
    ADD CONSTRAINT pharmacies_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: prescriptions prescriptions_medical_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_medical_record_id_fkey FOREIGN KEY (medical_record_id) REFERENCES public.medical_records(id) ON DELETE CASCADE;


--
-- Name: prescriptions prescriptions_pharmacy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_pharmacy_id_fkey FOREIGN KEY (pharmacy_id) REFERENCES public.pharmacies(id) ON DELETE SET NULL;


--
-- Name: prescriptions prescriptions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prescriptions
    ADD CONSTRAINT prescriptions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


