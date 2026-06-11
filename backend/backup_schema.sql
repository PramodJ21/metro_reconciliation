--
-- PostgreSQL database dump
--

\restrict pGekhw3iVuu02zzg8vSti0F5ybSooKp21Vc2TL6iMdDaKq3h7c45vUhBxAyfbaf

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ingestion_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ingestion_logs (
    id integer NOT NULL,
    filename character varying NOT NULL,
    app_name character varying NOT NULL,
    channel character varying NOT NULL,
    table_name character varying NOT NULL,
    row_count integer NOT NULL,
    status character varying DEFAULT 'STAGED'::character varying NOT NULL,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reverted_at timestamp without time zone
);


ALTER TABLE public.ingestion_logs OWNER TO postgres;

--
-- Name: ingestion_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ingestion_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ingestion_logs_id_seq OWNER TO postgres;

--
-- Name: ingestion_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ingestion_logs_id_seq OWNED BY public.ingestion_logs.id;


--
-- Name: manual_refunds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.manual_refunds (
    id integer NOT NULL,
    order_id character varying,
    ticket_no character varying,
    amount numeric,
    original_status character varying DEFAULT 'Liable for Refund'::character varying,
    updated_status character varying DEFAULT 'Manually Refunded'::character varying,
    note character varying,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.manual_refunds OWNER TO postgres;

--
-- Name: manual_refunds_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.manual_refunds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.manual_refunds_id_seq OWNER TO postgres;

--
-- Name: manual_refunds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.manual_refunds_id_seq OWNED BY public.manual_refunds.id;


--
-- Name: reconciliation_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reconciliation_results (
    id integer NOT NULL,
    app_source character varying,
    order_id character varying,
    ticket_no character varying,
    pg_ref_no character varying,
    amount numeric,
    transaction_time character varying,
    recon_status character varying,
    notes character varying,
    data_sources character varying,
    reconciled_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.reconciliation_results OWNER TO postgres;

--
-- Name: reconciliation_results_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reconciliation_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reconciliation_results_id_seq OWNER TO postgres;

--
-- Name: reconciliation_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reconciliation_results_id_seq OWNED BY public.reconciliation_results.id;


--
-- Name: stg_afc_transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public.stg_afc_transactions (
    id integer NOT NULL,
    s_no integer,
    date character varying,
    pass_name character varying,
    operator_name character varying,
    order_id character varying,
    ms_qr_no character varying,
    source_stn character varying,
    destination_stn character varying,
    slave_qr_no character varying,
    units integer,
    total_price numeric,
    file_source character varying
);


ALTER TABLE public.stg_afc_transactions OWNER TO postgres;

--
-- Name: stg_afc_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE UNLOGGED SEQUENCE public.stg_afc_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stg_afc_transactions_id_seq OWNER TO postgres;

--
-- Name: stg_afc_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stg_afc_transactions_id_seq OWNED BY public.stg_afc_transactions.id;


--
-- Name: stg_mobile_metroconnect3; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public.stg_mobile_metroconnect3 (
    id integer NOT NULL,
    ticket_no character varying,
    journey_id integer,
    booking_type character varying,
    no_of_tickets integer,
    status character varying,
    amount numeric,
    total_distance numeric,
    total_time numeric,
    total_stations character varying,
    booking_time character varying,
    valid_till character varying,
    requested_from character varying,
    trip_pass_id character varying,
    created_at character varying,
    updated_at character varying,
    file_source character varying
);


ALTER TABLE public.stg_mobile_metroconnect3 OWNER TO postgres;

--
-- Name: stg_mobile_metroconnect3_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE UNLOGGED SEQUENCE public.stg_mobile_metroconnect3_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stg_mobile_metroconnect3_id_seq OWNER TO postgres;

--
-- Name: stg_mobile_metroconnect3_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stg_mobile_metroconnect3_id_seq OWNED BY public.stg_mobile_metroconnect3.id;


--
-- Name: stg_mobile_mumbaione; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public.stg_mobile_mumbaione (
    id integer NOT NULL,
    ticket_number character varying,
    pg_reference_no character varying,
    mumbai_one_id character varying,
    source_station character varying,
    destination_station character varying,
    transportation_mode character varying,
    pto_name character varying,
    service_type character varying,
    passenger_type character varying,
    no_of_passenger integer,
    payment_amount numeric,
    ticket_type character varying,
    transaction_id character varying,
    transaction_date_time character varying,
    user_email_id character varying,
    user_mobile_no character varying,
    app_environment character varying,
    payment_status character varying,
    ticket_status character varying,
    file_source character varying
);


ALTER TABLE public.stg_mobile_mumbaione OWNER TO postgres;

--
-- Name: stg_mobile_mumbaione_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE UNLOGGED SEQUENCE public.stg_mobile_mumbaione_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stg_mobile_mumbaione_id_seq OWNER TO postgres;

--
-- Name: stg_mobile_mumbaione_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stg_mobile_mumbaione_id_seq OWNED BY public.stg_mobile_mumbaione.id;


--
-- Name: stg_mobile_ondc; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public.stg_mobile_ondc (
    id integer NOT NULL,
    order_id character varying,
    date character varying,
    transaction_id character varying,
    buyer character varying,
    number_of_tickets integer,
    price_rs numeric,
    status character varying,
    start_station character varying,
    end_station character varying,
    refund_amount numeric,
    file_source character varying
);


ALTER TABLE public.stg_mobile_ondc OWNER TO postgres;

--
-- Name: stg_mobile_ondc_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE UNLOGGED SEQUENCE public.stg_mobile_ondc_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stg_mobile_ondc_id_seq OWNER TO postgres;

--
-- Name: stg_mobile_ondc_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stg_mobile_ondc_id_seq OWNED BY public.stg_mobile_ondc.id;


--
-- Name: stg_pg_transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public.stg_pg_transactions (
    id integer NOT NULL,
    biller_id character varying,
    bank_id character varying,
    bank_ref_no character varying,
    pgi_ref_no character varying,
    ref_1 character varying,
    ref_2 character varying,
    ref_3 character varying,
    ref_4 character varying,
    ref_5 character varying,
    ref_6 character varying,
    ref_7 character varying,
    ref_8 character varying,
    filler character varying,
    date_of_txn character varying,
    settlement_date character varying,
    gross_amount numeric,
    charges numeric,
    gst numeric,
    net_amount numeric,
    refund_id character varying,
    refund_date character varying,
    refund_amount numeric,
    sub_txn_id character varying,
    transaction_type character varying,
    app_source character varying,
    file_source character varying
);


ALTER TABLE public.stg_pg_transactions OWNER TO postgres;

--
-- Name: stg_pg_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE UNLOGGED SEQUENCE public.stg_pg_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stg_pg_transactions_id_seq OWNER TO postgres;

--
-- Name: stg_pg_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stg_pg_transactions_id_seq OWNED BY public.stg_pg_transactions.id;


--
-- Name: ingestion_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingestion_logs ALTER COLUMN id SET DEFAULT nextval('public.ingestion_logs_id_seq'::regclass);


--
-- Name: manual_refunds id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_refunds ALTER COLUMN id SET DEFAULT nextval('public.manual_refunds_id_seq'::regclass);


--
-- Name: reconciliation_results id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliation_results ALTER COLUMN id SET DEFAULT nextval('public.reconciliation_results_id_seq'::regclass);


--
-- Name: stg_afc_transactions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_afc_transactions ALTER COLUMN id SET DEFAULT nextval('public.stg_afc_transactions_id_seq'::regclass);


--
-- Name: stg_mobile_metroconnect3 id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_metroconnect3 ALTER COLUMN id SET DEFAULT nextval('public.stg_mobile_metroconnect3_id_seq'::regclass);


--
-- Name: stg_mobile_mumbaione id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_mumbaione ALTER COLUMN id SET DEFAULT nextval('public.stg_mobile_mumbaione_id_seq'::regclass);


--
-- Name: stg_mobile_ondc id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_ondc ALTER COLUMN id SET DEFAULT nextval('public.stg_mobile_ondc_id_seq'::regclass);


--
-- Name: stg_pg_transactions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_pg_transactions ALTER COLUMN id SET DEFAULT nextval('public.stg_pg_transactions_id_seq'::regclass);


--
-- Name: ingestion_logs ingestion_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingestion_logs
    ADD CONSTRAINT ingestion_logs_pkey PRIMARY KEY (id);


--
-- Name: manual_refunds manual_refunds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_refunds
    ADD CONSTRAINT manual_refunds_pkey PRIMARY KEY (id);


--
-- Name: reconciliation_results reconciliation_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliation_results
    ADD CONSTRAINT reconciliation_results_pkey PRIMARY KEY (id);


--
-- Name: stg_afc_transactions stg_afc_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_afc_transactions
    ADD CONSTRAINT stg_afc_transactions_pkey PRIMARY KEY (id);


--
-- Name: stg_mobile_metroconnect3 stg_mobile_metroconnect3_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_metroconnect3
    ADD CONSTRAINT stg_mobile_metroconnect3_pkey PRIMARY KEY (id);


--
-- Name: stg_mobile_mumbaione stg_mobile_mumbaione_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_mumbaione
    ADD CONSTRAINT stg_mobile_mumbaione_pkey PRIMARY KEY (id);


--
-- Name: stg_mobile_ondc stg_mobile_ondc_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_mobile_ondc
    ADD CONSTRAINT stg_mobile_ondc_pkey PRIMARY KEY (id);


--
-- Name: stg_pg_transactions stg_pg_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stg_pg_transactions
    ADD CONSTRAINT stg_pg_transactions_pkey PRIMARY KEY (id);


--
-- Name: idx_ing_logs_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ing_logs_status ON public.ingestion_logs USING btree (status);


--
-- Name: idx_man_ref_ord_tkt; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_man_ref_ord_tkt ON public.manual_refunds USING btree (order_id, ticket_no);


--
-- Name: idx_recon_res_app; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recon_res_app ON public.reconciliation_results USING btree (app_source);


--
-- Name: idx_recon_res_ord_tkt; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recon_res_ord_tkt ON public.reconciliation_results USING btree (order_id, ticket_no);


--
-- Name: idx_recon_res_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recon_res_status ON public.reconciliation_results USING btree (recon_status);


--
-- Name: idx_stg_afc_filesrc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_afc_filesrc ON public.stg_afc_transactions USING btree (file_source);


--
-- Name: idx_stg_afc_op; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_afc_op ON public.stg_afc_transactions USING btree (operator_name);


--
-- Name: idx_stg_afc_ord; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_afc_ord ON public.stg_afc_transactions USING btree (order_id);


--
-- Name: idx_stg_afc_sqr; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_afc_sqr ON public.stg_afc_transactions USING btree (slave_qr_no);


--
-- Name: idx_stg_mob_m1_filesrc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_m1_filesrc ON public.stg_mobile_mumbaione USING btree (file_source);


--
-- Name: idx_stg_mob_m1_ord_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_m1_ord_id ON public.stg_mobile_mumbaione USING btree (mumbai_one_id);


--
-- Name: idx_stg_mob_m1_pg_ref; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_m1_pg_ref ON public.stg_mobile_mumbaione USING btree (pg_reference_no);


--
-- Name: idx_stg_mob_m1_tkt_no; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_m1_tkt_no ON public.stg_mobile_mumbaione USING btree (ticket_number);


--
-- Name: idx_stg_mob_mc3_filesrc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_mc3_filesrc ON public.stg_mobile_metroconnect3 USING btree (file_source);


--
-- Name: idx_stg_mob_mc3_tno; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_mc3_tno ON public.stg_mobile_metroconnect3 USING btree (ticket_no);


--
-- Name: idx_stg_mob_ondc_filesrc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_ondc_filesrc ON public.stg_mobile_ondc USING btree (file_source);


--
-- Name: idx_stg_mob_ondc_ord; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_mob_ondc_ord ON public.stg_mobile_ondc USING btree (order_id);


--
-- Name: idx_stg_pg_filesrc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_pg_filesrc ON public.stg_pg_transactions USING btree (file_source);


--
-- Name: idx_stg_pg_pgi_ref; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_pg_pgi_ref ON public.stg_pg_transactions USING btree (pgi_ref_no);


--
-- Name: idx_stg_pg_ref_1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_pg_ref_1 ON public.stg_pg_transactions USING btree (ref_1);


--
-- Name: idx_stg_pg_type_src; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_stg_pg_type_src ON public.stg_pg_transactions USING btree (transaction_type, app_source);


--
-- PostgreSQL database dump complete
--

\unrestrict pGekhw3iVuu02zzg8vSti0F5ybSooKp21Vc2TL6iMdDaKq3h7c45vUhBxAyfbaf

