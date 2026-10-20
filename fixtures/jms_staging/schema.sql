-- Structure-only snapshot. Load into an empty database.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `activity_feed`;
CREATE TABLE `activity_feed` (
  `activity_feed_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `action_by_id` int DEFAULT NULL,
  `action_by_type` varchar(20) DEFAULT NULL,
  `activity_type` varchar(100) DEFAULT NULL,
  `activity_description` text,
  `contact_id` int DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  PRIMARY KEY (`activity_feed_id`),
  KEY `contact_id` (`contact_id`),
  KEY `agency_id` (`agency_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `idx_activity_feed_ip_type_af_id` (`ip_case_id`,`activity_type`,`activity_feed_id` DESC),
  KEY `idx_activity_feed_gc_type_af_id` (`gc_case_id`,`activity_type`,`activity_feed_id` DESC),
  CONSTRAINT `activity_feed_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `activity_feed_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `activity_feed_ibfk_3` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `activity_feed_ibfk_4` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `activity_note`;
CREATE TABLE `activity_note` (
  `activity_note_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `text` text,
  `related_admins` varchar(255) DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `activity_feed_id` int DEFAULT NULL,
  PRIMARY KEY (`activity_note_id`),
  KEY `admin_id` (`admin_id`),
  KEY `activity_feed_id` (`activity_feed_id`),
  CONSTRAINT `activity_note_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `activity_note_ibfk_2` FOREIGN KEY (`activity_feed_id`) REFERENCES `activity_feed` (`activity_feed_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `admin`;
CREATE TABLE `admin` (
  `admin_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `calendar_view` varchar(5) DEFAULT 'week',
  `created` datetime DEFAULT NULL,
  `admin_type` varchar(50) DEFAULT NULL,
  `dev_admin` tinyint(1) DEFAULT '0',
  `email` varchar(255) DEFAULT NULL,
  `phone_number` varchar(25) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `title` varchar(50) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `email_key` varchar(10) DEFAULT NULL,
  `shared_auth_key` varchar(20) DEFAULT NULL,
  `gurgle_auth_key` varchar(32) DEFAULT NULL,
  `active_access_key` varchar(100) DEFAULT NULL,
  `email_client` varchar(10) DEFAULT NULL,
  `permissions` text,
  `custom_signature` text,
  `time_zone_pytz` varchar(100) DEFAULT 'UTC',
  `pricing_adjustments_allowed` tinyint(1) DEFAULT '0',
  `orchid_admin` tinyint(1) DEFAULT '0',
  `soft_deleted` tinyint(1) DEFAULT '0',
  `gurgle_alert_sent` tinyint(1) DEFAULT '0',
  `my_notepad` text,
  `automatically_log_emails` tinyint(1) DEFAULT NULL,
  `email_mailto_action` varchar(3) NOT NULL DEFAULT 'os',
  `historical_sync_timeframe` enum('MONTH','YEAR','FOREVER') DEFAULT NULL,
  `billing_contact` datetime DEFAULT NULL,
  `next_tasks_sort` varchar(13) DEFAULT NULL,
  PRIMARY KEY (`admin_id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `email_key` (`email_key`),
  UNIQUE KEY `gurgle_auth_key` (`gurgle_auth_key`),
  UNIQUE KEY `shared_auth_key` (`shared_auth_key`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `admin_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `admin_chk_1` CHECK ((`automatically_log_emails` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `admin_calendar_sync`;
CREATE TABLE `admin_calendar_sync` (
  `admin_calendar_sync_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int NOT NULL,
  `oauth_token_id` int NOT NULL,
  `calendar_id` varchar(255) DEFAULT NULL,
  `calendar_name` varchar(255) DEFAULT NULL,
  `status` enum('PENDING','ACTIVE','WILL_RETRY','RETRY_PAUSED','DISCONNECTED','ERROR') DEFAULT NULL,
  `sync_token` text,
  `last_sync_at` datetime DEFAULT NULL,
  `last_sync_error` text,
  `consecutive_failures` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `last_attempt_at` datetime DEFAULT NULL,
  `connection_state` enum('SYNCING','PAUSED','REMOVED') NOT NULL,
  `last_full_sync_at` datetime DEFAULT NULL,
  `disconnection_email_sent` datetime DEFAULT NULL,
  `account_id` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`admin_calendar_sync_id`),
  UNIQUE KEY `uq_admin_calendar_sync_admin_calendar` (`admin_id`,`calendar_id`),
  KEY `oauth_token_id` (`oauth_token_id`),
  CONSTRAINT `admin_calendar_sync_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `admin_calendar_sync_ibfk_2` FOREIGN KEY (`oauth_token_id`) REFERENCES `oauth_token` (`token_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `admin_chat_message`;
CREATE TABLE `admin_chat_message` (
  `admin_chat_message_id` int NOT NULL AUTO_INCREMENT,
  `admin_chat_session_id` int NOT NULL,
  `role` varchar(16) NOT NULL,
  `body` text,
  `meta` text,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`admin_chat_message_id`),
  KEY `admin_chat_session_id` (`admin_chat_session_id`),
  CONSTRAINT `admin_chat_message_ibfk_1` FOREIGN KEY (`admin_chat_session_id`) REFERENCES `admin_chat_session` (`admin_chat_session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `admin_chat_session`;
CREATE TABLE `admin_chat_session` (
  `admin_chat_session_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int NOT NULL,
  `title` varchar(160) DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `last_message_at` datetime DEFAULT NULL,
  `pending_report_sql` text,
  `pending_report_headers` text,
  `pending_report_title` varchar(255) DEFAULT NULL,
  `pending_report_custom_report_id` int DEFAULT NULL,
  PRIMARY KEY (`admin_chat_session_id`),
  KEY `ix_admin_chat_session_admin_last` (`admin_id`,`last_message_at`),
  CONSTRAINT `admin_chat_session_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency`;
CREATE TABLE `agency` (
  `agency_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_name` varchar(255) DEFAULT NULL,
  `address_1` varchar(100) DEFAULT NULL,
  `address_2` varchar(50) DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `state` varchar(50) DEFAULT NULL,
  `zip_code` varchar(10) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `fax` varchar(20) DEFAULT NULL,
  `sendgrid_from_email` varchar(100) DEFAULT NULL,
  `intake_alert_email` text,
  `intake_alert_email_gc` text,
  `intake_alert_email_ed` text,
  `fast_track_matching_type` varchar(10) DEFAULT NULL,
  `fast_track_admin_ip` int DEFAULT NULL,
  `fast_track_admin_gc` int DEFAULT NULL,
  `fast_track_admin_ed` int DEFAULT NULL,
  `cycle_order` varchar(10) DEFAULT NULL,
  `shared_auth_id` varchar(100) DEFAULT NULL,
  `shared_auth_sk` varchar(100) DEFAULT NULL,
  `logo_path` varchar(255) DEFAULT NULL,
  `favicon_path` varchar(255) DEFAULT NULL,
  `subdomain` varchar(40) DEFAULT NULL,
  `stripe_id` varchar(255) DEFAULT NULL,
  `subscription_info_id` int DEFAULT NULL,
  `website_url` varchar(255) DEFAULT NULL,
  `logo_height` int DEFAULT '0',
  `ed_start_anonymous` tinyint NOT NULL DEFAULT '1',
  `new_ed_age_dq` tinyint(1) DEFAULT '0',
  `past_ed_age_dq` tinyint(1) DEFAULT '0',
  `ed_bmi_dq` tinyint(1) DEFAULT '0',
  `new_ed_age_min` int DEFAULT NULL,
  `new_ed_age_max` int DEFAULT NULL,
  `past_ed_age_min` int DEFAULT NULL,
  `past_ed_age_max` int DEFAULT NULL,
  `ed_bmi_min` int DEFAULT NULL,
  `ed_bmi_max` int DEFAULT NULL,
  `gc_age_dq` tinyint(1) DEFAULT '0',
  `gc_bmi_dq` tinyint(1) DEFAULT '0',
  `gc_age_min` int DEFAULT NULL,
  `gc_age_max` int DEFAULT NULL,
  `gc_bmi_min` int DEFAULT NULL,
  `gc_bmi_max` int DEFAULT NULL,
  `gc_bmi_over` text,
  `gc_bmi_under` text,
  `gc_age_over` text,
  `gc_age_under` text,
  `ed_bmi_over` text,
  `ed_bmi_under` text,
  `new_ed_age_over` text,
  `past_ed_age_over` text,
  `past_ed_age_under` text,
  `ip_acceptance` text,
  `ip_rejection` text,
  `gc_acceptance` text,
  `gc_rejection` text,
  `ed_acceptance` text,
  `ed_rejection` text,
  `gc_fast_track_message` text,
  `ed_fast_track_message` text,
  `ip_fast_track_message` text,
  `welcome_email` text,
  `duplicate_email` text,
  `archived_account` text,
  `no_account_created` text,
  `profile_review_button_accept` varchar(25) DEFAULT NULL,
  `profile_review_button_deny` varchar(25) DEFAULT NULL,
  `profile_review_button_request` varchar(25) DEFAULT NULL,
  `hellosign_template` text,
  `resend_email_confirmation` text,
  `new_ed_age_under` text,
  `time_zone_pytz` varchar(100) DEFAULT 'UTC',
  `logo_width` int DEFAULT '0',
  `gc_profile_list` tinyint(1) DEFAULT '0',
  `always_display_gc_list` tinyint(1) DEFAULT '0',
  `gc_profile_list_users` tinyint(1) DEFAULT '0',
  `always_hide_profiles` tinyint(1) DEFAULT '0',
  `hide_ip_profiles` tinyint(1) DEFAULT '0',
  `hide_gc_profiles` tinyint(1) DEFAULT '0',
  `hide_ed_profiles` tinyint(1) DEFAULT '0',
  `ip_profile_visibility` text,
  `gc_profile_visibility` text,
  `ed_profile_visibility` text,
  `displayed_retrieval_questions` text,
  `current_products` varchar(255) DEFAULT NULL,
  `using_subscription` tinyint(1) DEFAULT '0',
  `ip_profile_column_width` text,
  `gc_profile_column_width` text,
  `ed_profile_column_width` text,
  `show_ed_with_approval` tinyint(1) DEFAULT '0',
  `ed_always_anonymous` tinyint(1) DEFAULT '0',
  `intake_alert_email_sd` text,
  `fast_track_admin_sd` int DEFAULT NULL,
  `sd_profile_visibility` text,
  `sd_profile_column_width` text,
  `gc_profile_list_additional_portals` tinyint(1) DEFAULT NULL,
  `use_custom_from_email` tinyint(1) DEFAULT '0',
  `chatbot_display_name` varchar(64) DEFAULT NULL,
  `email_sync_disconnect_alert_email` text,
  `billing_banner_active` datetime DEFAULT NULL,
  PRIMARY KEY (`agency_id`),
  UNIQUE KEY `agency_name` (`agency_name`),
  KEY `subscription_info_id` (`subscription_info_id`),
  CONSTRAINT `agency_ibfk_1` FOREIGN KEY (`subscription_info_id`) REFERENCES `subscription_info` (`subscription_info_id`),
  CONSTRAINT `agency_chk_1` CHECK ((`use_custom_from_email` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `agency_agent_settings`;
CREATE TABLE `agency_agent_settings` (
  `agency_agent_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `agent_key` varchar(32) NOT NULL,
  `ip_disabled_at` datetime DEFAULT NULL,
  `gc_disabled_at` datetime DEFAULT NULL,
  `ed_disabled_at` datetime DEFAULT NULL,
  `sd_disabled_at` datetime DEFAULT NULL,
  PRIMARY KEY (`agency_agent_settings_id`),
  UNIQUE KEY `uq_agency_agent_settings_agency_agent` (`agency_id`,`agent_key`),
  CONSTRAINT `agency_agent_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_calendar_sync_settings`;
CREATE TABLE `agency_calendar_sync_settings` (
  `agency_calendar_sync_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `lookback_days` int NOT NULL,
  `lookforward_days` int NOT NULL,
  `created` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  PRIMARY KEY (`agency_calendar_sync_settings_id`),
  UNIQUE KEY `uq_agency_calendar_sync_settings_agency` (`agency_id`),
  CONSTRAINT `agency_calendar_sync_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_chatbot_settings`;
CREATE TABLE `agency_chatbot_settings` (
  `agency_chatbot_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `ip_disabled_at` datetime DEFAULT NULL,
  `gc_disabled_at` datetime DEFAULT NULL,
  `ed_disabled_at` datetime DEFAULT NULL,
  `sd_disabled_at` datetime DEFAULT NULL,
  `display_name` varchar(64) DEFAULT NULL,
  `peek_message` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`agency_chatbot_settings_id`),
  UNIQUE KEY `uq_agency_chatbot_settings_agency` (`agency_id`),
  CONSTRAINT `agency_chatbot_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_colors`;
CREATE TABLE `agency_colors` (
  `colors_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `primary_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#823C82',
  `secondary_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#EED6F0',
  `button_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#823C82',
  `button_text_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#FFFFFF',
  `link_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#0091AE',
  `nav_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#823C82',
  `nav_text_color` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '#FFFFFF',
  PRIMARY KEY (`colors_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `agency_colors_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_contact_types`;
CREATE TABLE `agency_contact_types` (
  `agency_contact_types_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `supports_gc` tinyint(1) DEFAULT NULL,
  `supports_ed` tinyint(1) DEFAULT NULL,
  `supports_sd` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`agency_contact_types_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `agency_contact_types_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `agency_contact_types_chk_1` CHECK ((`supports_gc` in (0,1))),
  CONSTRAINT `agency_contact_types_chk_2` CHECK ((`supports_ed` in (0,1))),
  CONSTRAINT `agency_contact_types_chk_3` CHECK ((`supports_sd` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_custom_copy`;
CREATE TABLE `agency_custom_copy` (
  `agency_custom_copy_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `donor_database_copy` text,
  `sperm_donor_database_copy` text,
  PRIMARY KEY (`agency_custom_copy_id`),
  KEY `agency_custom_copy_ibfk_1` (`agency_id`),
  CONSTRAINT `agency_custom_copy_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_custom_responses`;
CREATE TABLE `agency_custom_responses` (
  `agency_custom_responses_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `ip_acceptance` text,
  `ip_rejection` text,
  `gc_acceptance` text,
  `gc_rejection` text,
  `ed_acceptance` text,
  `ed_rejection` text,
  `gc_fast_track_message` text,
  `ed_fast_track_message` text,
  `ip_fast_track_message` text,
  `duplicate_email` text,
  `archived_account` text,
  `no_account_created` text,
  `profile_review_button_accept` varchar(25) DEFAULT NULL,
  `profile_review_button_deny` varchar(25) DEFAULT NULL,
  `profile_review_button_request` varchar(25) DEFAULT NULL,
  `welcome_email` text,
  `ip_welcome_email` text,
  `gc_welcome_email` text,
  `ed_welcome_email` text,
  `np_user_welcome_email` text,
  `ip_rep_welcome_email` text,
  `hellosign_template` text,
  `resend_email_confirmation` text,
  `sd_acceptance` text,
  `sd_rejection` text,
  `sd_fast_track_message` text,
  `sd_welcome_email` text,
  PRIMARY KEY (`agency_custom_responses_id`),
  KEY `agency_custom_responses_ibfk_1` (`agency_id`),
  CONSTRAINT `agency_custom_responses_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_document`;
CREATE TABLE `agency_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `document_group` varchar(100) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `notes` text,
  PRIMARY KEY (`document_id`),
  KEY `agency_id` (`agency_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `agency_document_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `agency_document_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `agency_document_folder`;
CREATE TABLE `agency_document_folder` (
  `agency_document_folder_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `is_default` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`agency_document_folder_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_dq_settings`;
CREATE TABLE `agency_dq_settings` (
  `agency_dq_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `new_ed_age_dq` tinyint(1) DEFAULT '0',
  `past_ed_age_dq` tinyint(1) DEFAULT '0',
  `ed_bmi_dq` tinyint(1) DEFAULT '0',
  `new_ed_age_min` int DEFAULT NULL,
  `new_ed_age_max` int DEFAULT NULL,
  `past_ed_age_min` int DEFAULT NULL,
  `past_ed_age_max` int DEFAULT NULL,
  `ed_bmi_min` int DEFAULT NULL,
  `ed_bmi_max` int DEFAULT NULL,
  `gc_age_dq` tinyint(1) DEFAULT '0',
  `gc_bmi_dq` tinyint(1) DEFAULT '0',
  `gc_age_min` int DEFAULT NULL,
  `gc_age_max` int DEFAULT NULL,
  `gc_bmi_min` int DEFAULT NULL,
  `gc_bmi_max` int DEFAULT NULL,
  `gc_bmi_over` text,
  `gc_bmi_under` text,
  `gc_age_over` text,
  `gc_age_under` text,
  `ed_bmi_over` text,
  `ed_bmi_under` text,
  `new_ed_age_over` text,
  `new_ed_age_under` text,
  `past_ed_age_over` text,
  `past_ed_age_under` text,
  `sd_age_dq` tinyint(1) DEFAULT NULL,
  `sd_bmi_dq` tinyint(1) DEFAULT NULL,
  `sd_age_min` int DEFAULT NULL,
  `sd_age_max` int DEFAULT NULL,
  `sd_bmi_min` int DEFAULT NULL,
  `sd_bmi_max` int DEFAULT NULL,
  `sd_bmi_over` text,
  `sd_bmi_under` text,
  `sd_age_over` text,
  `sd_age_under` text,
  PRIMARY KEY (`agency_dq_settings_id`),
  KEY `agency_dq_settings_ibfk_1` (`agency_id`),
  CONSTRAINT `agency_dq_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `agency_dq_settings_chk_1` CHECK ((`sd_age_dq` in (0,1))),
  CONSTRAINT `agency_dq_settings_chk_2` CHECK ((`sd_bmi_dq` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_preferences`;
CREATE TABLE `agency_preferences` (
  `agency_preferences_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `cycle_order` varchar(10) DEFAULT NULL,
  `ed_start_anonymous` tinyint(1) NOT NULL DEFAULT '1',
  `ed_always_anonymous` tinyint(1) DEFAULT '0',
  `gc_profile_list` tinyint(1) DEFAULT '0',
  `gc_profile_list_users` tinyint(1) DEFAULT '0',
  `always_display_gc_list` tinyint(1) DEFAULT '0',
  `always_hide_profiles` tinyint(1) DEFAULT '0',
  `hide_ip_profiles` tinyint(1) DEFAULT '0',
  `hide_gc_profiles` tinyint(1) DEFAULT '0',
  `hide_ed_profiles` tinyint(1) DEFAULT '0',
  `displayed_retrieval_questions` text,
  `show_ed_with_approval` tinyint(1) DEFAULT '0',
  `lock_matching_type` tinyint(1) DEFAULT '0',
  `gc_profile_card_prefs` text,
  `ed_profile_card_prefs` text,
  `sd_cycle_order` varchar(10) DEFAULT NULL,
  `sd_start_anonymous` tinyint(1) NOT NULL,
  `sd_always_anonymous` tinyint(1) DEFAULT NULL,
  `hide_sd_profiles` tinyint(1) DEFAULT NULL,
  `sd_displayed_retrieval_questions` text,
  `show_sd_with_approval` tinyint(1) DEFAULT NULL,
  `sd_profile_card_prefs` text,
  `use_default_matchsheets` tinyint(1) DEFAULT '1',
  `ed_display_nickname_only` tinyint(1) DEFAULT NULL,
  `gc_profile_list_additional_portals` tinyint(1) DEFAULT NULL,
  `ed_profile_list` tinyint(1) DEFAULT NULL,
  `ed_profile_list_users` tinyint(1) DEFAULT NULL,
  `ed_profile_list_additional_portals` tinyint(1) DEFAULT NULL,
  `sd_profile_list` tinyint(1) DEFAULT NULL,
  `sd_profile_list_users` tinyint(1) DEFAULT NULL,
  `sd_profile_list_additional_portals` tinyint(1) DEFAULT NULL,
  `ip_profile_list` tinyint(1) DEFAULT NULL,
  `ip_profile_card_prefs` text,
  `sd_display_nickname_only` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`agency_preferences_id`),
  KEY `agency_preferences_ibfk_1` (`agency_id`),
  CONSTRAINT `agency_preferences_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `agency_preferences_chk_1` CHECK ((`sd_start_anonymous` in (0,1))),
  CONSTRAINT `agency_preferences_chk_10` CHECK ((`ed_profile_list_additional_portals` in (0,1))),
  CONSTRAINT `agency_preferences_chk_11` CHECK ((`sd_profile_list` in (0,1))),
  CONSTRAINT `agency_preferences_chk_12` CHECK ((`sd_profile_list_users` in (0,1))),
  CONSTRAINT `agency_preferences_chk_13` CHECK ((`sd_profile_list_additional_portals` in (0,1))),
  CONSTRAINT `agency_preferences_chk_14` CHECK ((`ip_profile_list` in (0,1))),
  CONSTRAINT `agency_preferences_chk_15` CHECK ((`sd_display_nickname_only` in (0,1))),
  CONSTRAINT `agency_preferences_chk_2` CHECK ((`sd_always_anonymous` in (0,1))),
  CONSTRAINT `agency_preferences_chk_3` CHECK ((`hide_sd_profiles` in (0,1))),
  CONSTRAINT `agency_preferences_chk_4` CHECK ((`show_sd_with_approval` in (0,1))),
  CONSTRAINT `agency_preferences_chk_5` CHECK ((`use_default_matchsheets` in (0,1))),
  CONSTRAINT `agency_preferences_chk_6` CHECK ((`ed_display_nickname_only` in (0,1))),
  CONSTRAINT `agency_preferences_chk_7` CHECK ((`gc_profile_list_additional_portals` in (0,1))),
  CONSTRAINT `agency_preferences_chk_8` CHECK ((`ed_profile_list` in (0,1))),
  CONSTRAINT `agency_preferences_chk_9` CHECK ((`ed_profile_list_users` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_sms_settings`;
CREATE TABLE `agency_sms_settings` (
  `agency_sms_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `sms_enabled` tinyint(1) DEFAULT NULL,
  `twilio_messaging_service_sid` varchar(50) DEFAULT NULL,
  `default_country_code` varchar(5) DEFAULT NULL,
  `segment_cap` int DEFAULT NULL,
  `unknown_opt_in_behavior` varchar(20) DEFAULT NULL,
  `daily_send_limit` int DEFAULT NULL,
  `webhook_token` varchar(36) NOT NULL,
  `admin_opt_in_cooldown_minutes` int DEFAULT '720',
  `daily_limit_warning_sent_at` datetime DEFAULT NULL,
  `twilio_subaccount_sid` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`agency_sms_settings_id`),
  UNIQUE KEY `agency_id` (`agency_id`),
  UNIQUE KEY `uq_agency_sms_settings_webhook_token` (`webhook_token`),
  CONSTRAINT `agency_sms_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `agency_sms_settings_chk_1` CHECK ((`sms_enabled` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `agency_team`;
CREATE TABLE `agency_team` (
  `agency_team_id` int NOT NULL AUTO_INCREMENT,
  `team_name` varchar(100) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  PRIMARY KEY (`agency_team_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `agency_team_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `agency_team_admin`;
CREATE TABLE `agency_team_admin` (
  `agency_team_admin_id` int NOT NULL AUTO_INCREMENT,
  `agency_team_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `admin_team_type` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`agency_team_admin_id`),
  KEY `agency_team_id` (`agency_team_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `agency_team_admin_ibfk_1` FOREIGN KEY (`agency_team_id`) REFERENCES `agency_team` (`agency_team_id`) ON DELETE CASCADE,
  CONSTRAINT `agency_team_admin_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `agency_workview_settings`;
CREATE TABLE `agency_workview_settings` (
  `agency_workview_settings_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `stage` varchar(50) NOT NULL,
  `on_track_upper` int NOT NULL,
  `at_risk_upper` int NOT NULL,
  `created` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  PRIMARY KEY (`agency_workview_settings_id`),
  UNIQUE KEY `uq_agency_workview_settings_agency_stage` (`agency_id`,`stage`),
  CONSTRAINT `agency_workview_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE `alembic_version` (
  `version_num` varchar(255) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `archive_reason`;
CREATE TABLE `archive_reason` (
  `archive_reason_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `reason` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`archive_reason_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `archive_reason_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `calculator_custom_response`;
CREATE TABLE `calculator_custom_response` (
  `custom_response_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `calculator_type` varchar(100) DEFAULT NULL,
  `param_1` varchar(100) DEFAULT NULL,
  `param_2` varchar(100) DEFAULT NULL,
  `custom_image_1` varchar(225) DEFAULT NULL,
  `custom_display_text_1` varchar(225) DEFAULT NULL,
  `custom_display_text_2` varchar(225) DEFAULT NULL,
  PRIMARY KEY (`custom_response_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `calculator_custom_response_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `calendar_event`;
CREATE TABLE `calendar_event` (
  `calendar_event_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `title` varchar(100) DEFAULT NULL,
  `date` date DEFAULT NULL,
  `time` time DEFAULT NULL,
  `date_end` date DEFAULT NULL,
  `time_end` time DEFAULT NULL,
  `event_type` varchar(100) DEFAULT NULL,
  `attendees` varchar(255) DEFAULT NULL,
  `admin_attendees` varchar(255) DEFAULT NULL,
  `location` varchar(100) DEFAULT NULL,
  `link` varchar(255) DEFAULT NULL,
  `description` text,
  `external_id` varchar(255) DEFAULT NULL,
  `external_source` varchar(10) DEFAULT NULL,
  `external_etag` varchar(255) DEFAULT NULL,
  `calendar_sync_id` int DEFAULT NULL,
  `synced_at` datetime DEFAULT NULL,
  `participants` text,
  `skip_resync` tinyint(1) NOT NULL DEFAULT '0',
  `external_link` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`calendar_event_id`),
  UNIQUE KEY `uq_calendar_event_sync_external` (`calendar_sync_id`,`external_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `user_id` (`user_id`),
  KEY `admin_id` (`admin_id`),
  KEY `ix_calendar_event_external` (`external_id`,`external_source`),
  CONSTRAINT `calendar_event_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `calendar_event_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `calendar_event_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `calendar_event_ibfk_4` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_calendar_event_calendar_sync_id` FOREIGN KEY (`calendar_sync_id`) REFERENCES `admin_calendar_sync` (`admin_calendar_sync_id`) ON DELETE SET NULL,
  CONSTRAINT `calendar_event_chk_1` CHECK ((`skip_resync` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `campaign`;
CREATE TABLE `campaign` (
  `campaign_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `internal_title` varchar(255) DEFAULT NULL,
  `internal_description` text,
  `stage` varchar(50) DEFAULT NULL,
  `case_type` varchar(50) DEFAULT NULL,
  `day_trigger` int DEFAULT NULL,
  `start_trigger` varchar(20) DEFAULT NULL,
  `start_trigger_val` varchar(100) DEFAULT NULL,
  `end_trigger` varchar(20) DEFAULT NULL,
  `end_trigger_val` varchar(100) DEFAULT NULL,
  `start_mode` enum('IMMEDIATE','HOURS','DAYS') NOT NULL DEFAULT 'DAYS',
  PRIMARY KEY (`campaign_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `campaign_flow`;
CREATE TABLE `campaign_flow` (
  `campaign_flow_id` int NOT NULL AUTO_INCREMENT,
  `campaign_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `flow_type` varchar(10) DEFAULT NULL,
  `email_template_id` int DEFAULT NULL,
  `sms_template_id` int DEFAULT NULL,
  `interval` int DEFAULT NULL,
  PRIMARY KEY (`campaign_flow_id`),
  KEY `campaign_id` (`campaign_id`),
  KEY `email_template_id` (`email_template_id`),
  KEY `sms_template_id` (`sms_template_id`),
  CONSTRAINT `campaign_flow_ibfk_1` FOREIGN KEY (`campaign_id`) REFERENCES `campaign` (`campaign_id`) ON DELETE CASCADE,
  CONSTRAINT `campaign_flow_ibfk_2` FOREIGN KEY (`email_template_id`) REFERENCES `email_template` (`email_template_id`) ON DELETE CASCADE,
  CONSTRAINT `campaign_flow_ibfk_3` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_campaign`;
CREATE TABLE `case_campaign` (
  `case_campaign_id` int NOT NULL AUTO_INCREMENT,
  `campaign_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `assigned_ip_case` int DEFAULT NULL,
  `assigned_gc_case` int DEFAULT NULL,
  `internal_title` varchar(100) DEFAULT NULL,
  `internal_description` varchar(255) DEFAULT NULL,
  `stage` varchar(50) DEFAULT NULL,
  `case_type` varchar(25) DEFAULT NULL,
  `day_trigger` int DEFAULT NULL,
  `start_trigger` varchar(20) DEFAULT NULL,
  `start_trigger_val` varchar(100) DEFAULT NULL,
  `end_trigger` varchar(20) DEFAULT NULL,
  `end_trigger_val` varchar(100) DEFAULT NULL,
  `flow_status` varchar(20) DEFAULT NULL,
  `flow_next` int DEFAULT NULL,
  `flow_date` date DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `start_mode` enum('IMMEDIATE','HOURS','DAYS') NOT NULL DEFAULT 'DAYS',
  PRIMARY KEY (`case_campaign_id`),
  KEY `assigned_gc_case` (`assigned_gc_case`),
  KEY `campaign_id` (`campaign_id`),
  KEY `flow_next` (`flow_next`),
  KEY `assigned_ip_case` (`assigned_ip_case`),
  CONSTRAINT `case_campaign_ibfk_1` FOREIGN KEY (`assigned_gc_case`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_campaign_ibfk_2` FOREIGN KEY (`campaign_id`) REFERENCES `campaign` (`campaign_id`) ON DELETE SET NULL,
  CONSTRAINT `case_campaign_ibfk_3` FOREIGN KEY (`flow_next`) REFERENCES `case_campaign_flow` (`case_campaign_flow_id`) ON DELETE CASCADE,
  CONSTRAINT `case_campaign_ibfk_4` FOREIGN KEY (`assigned_ip_case`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_campaign_flow`;
CREATE TABLE `case_campaign_flow` (
  `case_campaign_flow_id` int NOT NULL AUTO_INCREMENT,
  `case_campaign_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `flow_type` varchar(10) DEFAULT NULL,
  `email_template_id` int DEFAULT NULL,
  `sms_template_id` int DEFAULT NULL,
  `interval` int DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  PRIMARY KEY (`case_campaign_flow_id`),
  KEY `case_campaign_id` (`case_campaign_id`),
  KEY `email_template_id` (`email_template_id`),
  KEY `sms_template_id` (`sms_template_id`),
  CONSTRAINT `case_campaign_flow_ibfk_1` FOREIGN KEY (`case_campaign_id`) REFERENCES `case_campaign` (`case_campaign_id`) ON DELETE CASCADE,
  CONSTRAINT `case_campaign_flow_ibfk_2` FOREIGN KEY (`email_template_id`) REFERENCES `email_template` (`email_template_id`) ON DELETE CASCADE,
  CONSTRAINT `case_campaign_flow_ibfk_3` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_closing_details`;
CREATE TABLE `case_closing_details` (
  `case_closing_detail_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `surrogate_relationship` varchar(255) DEFAULT NULL,
  `agency_relationship` varchar(255) DEFAULT NULL,
  `clinic_relationship` varchar(255) DEFAULT NULL,
  `sibling_journey` varchar(255) DEFAULT NULL,
  `matchtime_expected` varchar(255) DEFAULT NULL,
  `legal_team_relationship` varchar(255) DEFAULT NULL,
  `remaining_issues` varchar(255) DEFAULT NULL,
  `local_counsel_issues` varchar(255) DEFAULT NULL,
  `contract_attorney_issues` varchar(255) DEFAULT NULL,
  `accounting_team_relationship` varchar(255) DEFAULT NULL,
  `funds_held` varchar(255) DEFAULT NULL,
  `contract_length` varchar(100) DEFAULT NULL,
  `final_refund` date DEFAULT NULL,
  `ip_overall_observations` varchar(255) DEFAULT NULL,
  `ip_surrogate_relationship` varchar(255) DEFAULT NULL,
  `ip_experience_recommendations` varchar(255) DEFAULT NULL,
  `recommend_ip_return` varchar(255) DEFAULT NULL,
  `ip_reference_recommendation` varchar(255) DEFAULT NULL,
  `gc_overall_observations` varchar(255) DEFAULT NULL,
  `surrogate_ip_relationship` varchar(255) DEFAULT NULL,
  `surrogate_complications` varchar(255) DEFAULT NULL,
  `surrogate_experience_recommendations` varchar(255) DEFAULT NULL,
  `surrogate_grade` varchar(100) DEFAULT NULL,
  `recommend_surrogate_return` varchar(255) DEFAULT NULL,
  `save_pdf` datetime DEFAULT NULL,
  PRIMARY KEY (`case_closing_detail_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `case_closing_details_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_closing_details_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_contract`;
CREATE TABLE `case_contract` (
  `case_contract_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `updated_by_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `contract_title` varchar(255) DEFAULT NULL,
  `contract` mediumtext,
  PRIMARY KEY (`case_contract_id`),
  KEY `agency_id` (`agency_id`),
  KEY `updated_by_id` (`updated_by_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `case_contract_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE SET NULL,
  CONSTRAINT `case_contract_ibfk_2` FOREIGN KEY (`updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_contract_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_date_based_todo`;
CREATE TABLE `case_date_based_todo` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `snippet_id` int DEFAULT NULL,
  `template_todo_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `task_assigned_to_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT NULL,
  `task_title` varchar(255) DEFAULT NULL,
  `task_status` varchar(30) DEFAULT NULL,
  `task_description` text,
  `must_be_completed_by` date DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `minutes_to_complete` int DEFAULT NULL,
  `task_type` varchar(20) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `last_updated_by` int DEFAULT NULL,
  `completed_by_id` int DEFAULT NULL,
  `original_due_date` date DEFAULT NULL,
  `is_addition` tinyint(1) DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `completed_by_id` (`completed_by_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `last_updated_by` (`last_updated_by`),
  KEY `snippet_id` (`snippet_id`),
  KEY `task_assigned_to_id` (`task_assigned_to_id`),
  KEY `template_todo_id` (`template_todo_id`),
  CONSTRAINT `case_date_based_todo_ibfk_1` FOREIGN KEY (`completed_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_4` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_5` FOREIGN KEY (`last_updated_by`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_6` FOREIGN KEY (`snippet_id`) REFERENCES `case_date_based_todo_snippet` (`snippet_id`) ON DELETE CASCADE,
  CONSTRAINT `case_date_based_todo_ibfk_7` FOREIGN KEY (`task_assigned_to_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_date_based_todo_ibfk_8` FOREIGN KEY (`template_todo_id`) REFERENCES `date_based_todo_template` (`todo_template_id`) ON DELETE CASCADE,
  CONSTRAINT `case_date_based_todo_chk_1` CHECK ((`flagged` in (0,1))),
  CONSTRAINT `case_date_based_todo_chk_2` CHECK ((`is_addition` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_date_based_todo_snippet`;
CREATE TABLE `case_date_based_todo_snippet` (
  `snippet_id` int NOT NULL AUTO_INCREMENT,
  `template_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `case_type` varchar(30) DEFAULT NULL,
  `reference_date_type` varchar(50) DEFAULT NULL,
  `reference_date` date DEFAULT NULL,
  PRIMARY KEY (`snippet_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `template_id` (`template_id`),
  CONSTRAINT `case_date_based_todo_snippet_ibfk_1` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_date_based_todo_snippet_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_date_based_todo_snippet_ibfk_3` FOREIGN KEY (`template_id`) REFERENCES `date_based_todo_snippet_template` (`snippet_template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_document`;
CREATE TABLE `case_document` (
  `case_document_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `custom_task_id` int DEFAULT NULL,
  `external_provider_id` int DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `uploaded_by_id` int DEFAULT NULL,
  `uploaded_by_type` varchar(20) DEFAULT NULL,
  `is_contract` tinyint(1) DEFAULT NULL,
  `notes` text,
  `document_group` varchar(40) DEFAULT NULL,
  `folder_id` int DEFAULT NULL,
  `viewable_by` varchar(255) DEFAULT NULL,
  `pinned_document` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`case_document_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `folder_id` (`folder_id`),
  KEY `custom_task_id` (`custom_task_id`),
  CONSTRAINT `case_document_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_document_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_document_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `agency_document_folder` (`agency_document_folder_id`) ON DELETE RESTRICT,
  CONSTRAINT `case_document_ibfk_4` FOREIGN KEY (`custom_task_id`) REFERENCES `custom_task` (`task_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_email`;
CREATE TABLE `case_email` (
  `case_email_id` int NOT NULL AUTO_INCREMENT,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `email_message_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `is_automatic_log` tinyint(1) DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`case_email_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `email_message_id` (`email_message_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `case_email_ibfk_1` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_email_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_email_ibfk_3` FOREIGN KEY (`email_message_id`) REFERENCES `email_message` (`email_message_id`) ON DELETE CASCADE,
  CONSTRAINT `case_email_ibfk_4` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `case_email_chk_1` CHECK ((`is_automatic_log` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_log`;
CREATE TABLE `case_log` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `log_date` date DEFAULT NULL,
  `log_time` time DEFAULT NULL,
  `log_type` varchar(255) DEFAULT NULL,
  `log_title` varchar(255) DEFAULT NULL,
  `log_description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `log_outcome` varchar(50) DEFAULT NULL,
  `last_updated_dt` datetime DEFAULT NULL,
  `last_updated_by_id` int DEFAULT NULL,
  `log_subtype` varchar(255) DEFAULT NULL,
  `sender` varchar(255) DEFAULT NULL,
  `recipients` varchar(255) DEFAULT NULL,
  `text_message_id` int DEFAULT NULL,
  `sync_source` varchar(20) DEFAULT NULL,
  `source_event_id` int DEFAULT NULL,
  `is_automatic_log` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`log_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `case_log_ibfk_4` (`last_updated_by_id`),
  KEY `fk_case_log_text_message_id` (`text_message_id`),
  KEY `fk_case_log_source_event_id` (`source_event_id`),
  CONSTRAINT `case_log_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `case_log_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_log_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_log_ibfk_4` FOREIGN KEY (`last_updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_case_log_source_event_id` FOREIGN KEY (`source_event_id`) REFERENCES `calendar_event` (`calendar_event_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_case_log_text_message_id` FOREIGN KEY (`text_message_id`) REFERENCES `text_message` (`text_message_id`) ON DELETE SET NULL,
  CONSTRAINT `case_log_chk_1` CHECK ((`is_automatic_log` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_match_sheet`;
CREATE TABLE `case_match_sheet` (
  `sheet_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `coordinator_phone_number` varchar(50) DEFAULT NULL,
  `coordinator_fax` varchar(50) DEFAULT NULL,
  `gc_marital_status` varchar(100) DEFAULT NULL,
  `gc_spouse_name` varchar(255) DEFAULT NULL,
  `gc_spouse_dob` date DEFAULT NULL,
  `gc_spouse_email` varchar(255) DEFAULT NULL,
  `ed_skype` varchar(255) DEFAULT NULL,
  `ed_lmp` date DEFAULT NULL,
  `ed_bcp` varchar(255) DEFAULT NULL,
  `ed_compensation` varchar(255) DEFAULT NULL,
  `ed_children` varchar(255) DEFAULT NULL,
  `ed_distance_from_clinic` varchar(255) DEFAULT NULL,
  `ed_blackout` text,
  `delivery_hospital` varchar(255) DEFAULT NULL,
  `out_of_town` varchar(255) DEFAULT NULL,
  `discuss_number_embryos_transfer` varchar(255) DEFAULT NULL,
  `discuss_termination` varchar(255) DEFAULT NULL,
  `health_insurance_coverage` varchar(255) DEFAULT NULL,
  `health_insurance_company` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians_street_address` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians_city` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians_state` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians_zip` varchar(255) DEFAULT NULL,
  `ip_alternative_guardians_country` varchar(255) DEFAULT NULL,
  `donor_egg_or_sperm` varchar(255) DEFAULT NULL,
  `special_requests` varchar(255) DEFAULT NULL,
  `misc` text,
  `custom_visibility` text,
  `m_md_coordinator_name` varchar(255) DEFAULT NULL,
  `deleted` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`sheet_id`),
  KEY `case_id` (`case_id`),
  CONSTRAINT `case_match_sheet_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_match_sheet_answer`;
CREATE TABLE `case_match_sheet_answer` (
  `answer_id` int NOT NULL AUTO_INCREMENT,
  `case_sheet_id` int NOT NULL,
  `question_id` int NOT NULL,
  `visible` tinyint(1) DEFAULT NULL,
  `answer` text,
  PRIMARY KEY (`answer_id`),
  KEY `case_sheet_id` (`case_sheet_id`),
  KEY `question_id` (`question_id`),
  CONSTRAINT `case_match_sheet_answer_ibfk_1` FOREIGN KEY (`case_sheet_id`) REFERENCES `case_match_sheet_template` (`sheet_id`) ON DELETE CASCADE,
  CONSTRAINT `case_match_sheet_answer_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `match_sheet_question` (`question_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_match_sheet_template`;
CREATE TABLE `case_match_sheet_template` (
  `sheet_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int NOT NULL,
  `parent_match_sheet_id` int NOT NULL,
  `show_match_dates` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `phone` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`sheet_id`),
  KEY `case_id` (`case_id`),
  KEY `parent_match_sheet_id` (`parent_match_sheet_id`),
  CONSTRAINT `case_match_sheet_template_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_match_sheet_template_ibfk_2` FOREIGN KEY (`parent_match_sheet_id`) REFERENCES `match_sheet_template` (`match_sheet_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_milestone`;
CREATE TABLE `case_milestone` (
  `case_milestone_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `order` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `completed` datetime DEFAULT NULL,
  PRIMARY KEY (`case_milestone_id`),
  KEY `case_id` (`case_id`),
  CONSTRAINT `case_milestone_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_note`;
CREATE TABLE `case_note` (
  `note_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `tags` varchar(255) DEFAULT NULL,
  `note` text,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `admins` text,
  `pinned` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`note_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `ip_case_id` (`ip_case_id`),
  CONSTRAINT `case_note_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_note_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_note_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_party`;
CREATE TABLE `case_party` (
  `party_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `np_user_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `team_visibility` tinyint(1) DEFAULT '1',
  `party_type` varchar(50) DEFAULT NULL,
  `contract_role` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`party_id`),
  KEY `user_id` (`user_id`),
  KEY `admin_id` (`admin_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `case_party_ibfk_90` (`np_user_id`),
  KEY `idx_case_party_ip_case_admin` (`ip_case_id`,`admin_id`),
  KEY `idx_case_party_gc_case_admin` (`gc_case_id`,`admin_id`),
  CONSTRAINT `case_party_ibfk_1` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_party_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_party_ibfk_3` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `case_party_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `case_party_ibfk_5` FOREIGN KEY (`np_user_id`) REFERENCES `user_np` (`np_user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_provider`;
CREATE TABLE `case_provider` (
  `case_provider_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `provider_user_id` int DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `match_sheet_display` tinyint(1) DEFAULT NULL,
  `provider_type` varchar(50) DEFAULT NULL,
  `provider_notes` text,
  `active` tinyint(1) DEFAULT NULL,
  `doctor_id` int DEFAULT NULL,
  `nurse_id` int DEFAULT NULL,
  `transfer_type` varchar(10) DEFAULT NULL,
  `user_type` varchar(10) DEFAULT NULL,
  `removal_reason` text,
  PRIMARY KEY (`case_provider_id`),
  KEY `provider_user_id` (`provider_user_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `doctor_id` (`doctor_id`),
  KEY `nurse_id` (`nurse_id`),
  CONSTRAINT `case_provider_ibfk_1` FOREIGN KEY (`provider_user_id`) REFERENCES `provider_user` (`provider_user_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_ibfk_2` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_ibfk_3` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_ibfk_4` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_ibfk_5` FOREIGN KEY (`doctor_id`) REFERENCES `clinic_contact` (`clinic_contact_id`) ON DELETE SET NULL,
  CONSTRAINT `case_provider_ibfk_6` FOREIGN KEY (`nurse_id`) REFERENCES `clinic_contact` (`clinic_contact_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `case_provider_external`;
CREATE TABLE `case_provider_external` (
  `case_provider_id` int NOT NULL AUTO_INCREMENT,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `provider_id_external` int DEFAULT NULL,
  `removed` datetime DEFAULT NULL,
  `removed_by_id` int DEFAULT NULL,
  `removal_reason` text,
  `provider_visibility_enabled` datetime DEFAULT NULL,
  `flags` int NOT NULL,
  PRIMARY KEY (`case_provider_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `removed_by_id` (`removed_by_id`),
  CONSTRAINT `case_provider_external_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`),
  CONSTRAINT `case_provider_external_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`),
  CONSTRAINT `case_provider_external_ibfk_3` FOREIGN KEY (`removed_by_id`) REFERENCES `admin` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_provider_external_cycle`;
CREATE TABLE `case_provider_external_cycle` (
  `association_id` int NOT NULL AUTO_INCREMENT,
  `case_provider_id` int DEFAULT NULL,
  `delivery_id` int DEFAULT NULL,
  `lab_id` int DEFAULT NULL,
  `pregnancy_id` int DEFAULT NULL,
  `retrieval_id` int DEFAULT NULL,
  `transfer_id` int DEFAULT NULL,
  `sd_retrieval_id` int DEFAULT NULL,
  PRIMARY KEY (`association_id`),
  KEY `case_provider_id` (`case_provider_id`),
  KEY `delivery_id` (`delivery_id`),
  KEY `lab_id` (`lab_id`),
  KEY `pregnancy_id` (`pregnancy_id`),
  KEY `retrieval_id` (`retrieval_id`),
  KEY `transfer_id` (`transfer_id`),
  KEY `sd_retrieval_id` (`sd_retrieval_id`),
  CONSTRAINT `case_provider_external_cycle_ibfk_1` FOREIGN KEY (`case_provider_id`) REFERENCES `case_provider_external` (`case_provider_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_2` FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_3` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`lab_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_4` FOREIGN KEY (`pregnancy_id`) REFERENCES `pregnancy` (`pregnancy_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_5` FOREIGN KEY (`retrieval_id`) REFERENCES `retrieval` (`retrieval_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_6` FOREIGN KEY (`transfer_id`) REFERENCES `transfer` (`transfer_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_cycle_ibfk_7` FOREIGN KEY (`sd_retrieval_id`) REFERENCES `sd_retrieval` (`sd_retrieval_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_provider_external_document`;
CREATE TABLE `case_provider_external_document` (
  `case_provider_id` int NOT NULL,
  `case_document_id` int NOT NULL,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  PRIMARY KEY (`case_provider_id`,`case_document_id`),
  KEY `case_document_id` (`case_document_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `case_provider_external_document_ibfk_1` FOREIGN KEY (`case_provider_id`) REFERENCES `case_provider_external` (`case_provider_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_document_ibfk_2` FOREIGN KEY (`case_document_id`) REFERENCES `case_document` (`case_document_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_document_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_provider_external_matchsheet`;
CREATE TABLE `case_provider_external_matchsheet` (
  `association_id` int NOT NULL AUTO_INCREMENT,
  `case_provider_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `case_sheet_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `discriminator` varchar(5) DEFAULT NULL,
  PRIMARY KEY (`association_id`),
  KEY `case_provider_id` (`case_provider_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `case_sheet_id` (`case_sheet_id`),
  CONSTRAINT `case_provider_external_matchsheet_ibfk_1` FOREIGN KEY (`case_provider_id`) REFERENCES `case_provider_external` (`case_provider_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_matchsheet_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_external_matchsheet_ibfk_3` FOREIGN KEY (`case_sheet_id`) REFERENCES `case_match_sheet_template` (`sheet_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_provider_matchsheet`;
CREATE TABLE `case_provider_matchsheet` (
  `case_provider_id` int NOT NULL,
  `case_sheet_id` int NOT NULL,
  PRIMARY KEY (`case_provider_id`,`case_sheet_id`),
  KEY `case_sheet_id` (`case_sheet_id`),
  CONSTRAINT `case_provider_matchsheet_ibfk_1` FOREIGN KEY (`case_provider_id`) REFERENCES `case_provider` (`case_provider_id`) ON DELETE CASCADE,
  CONSTRAINT `case_provider_matchsheet_ibfk_2` FOREIGN KEY (`case_sheet_id`) REFERENCES `case_match_sheet_template` (`sheet_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `case_task`;
CREATE TABLE `case_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `task_assigned_to_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT '0',
  `task_title` varchar(255) DEFAULT NULL,
  `task_description` text,
  `task_status` varchar(30) DEFAULT NULL,
  `must_be_completed_by` date DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `minutes_to_complete` int DEFAULT '60',
  `task_type` varchar(20) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `group_id` varchar(100) DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `task_repeat` varchar(10) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `last_updated_by` int DEFAULT NULL,
  `completed_by_id` int DEFAULT NULL,
  `is_addition` tinyint(1) DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `snippet_id` int DEFAULT NULL,
  `original_due_date` date DEFAULT NULL,
  `due_date_updated_by_id` int DEFAULT NULL,
  `due_date_last_updated` date DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `task_assigned_to_id` (`task_assigned_to_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `case_task_ibfk_5` (`last_updated_by`),
  KEY `case_task_ibfk_6` (`completed_by_id`),
  KEY `snippet_id` (`snippet_id`),
  KEY `due_date_updated_by_id` (`due_date_updated_by_id`),
  CONSTRAINT `case_task_ibfk_1` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_task_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_task_ibfk_3` FOREIGN KEY (`task_assigned_to_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_task_ibfk_4` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `case_task_ibfk_5` FOREIGN KEY (`last_updated_by`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_task_ibfk_6` FOREIGN KEY (`completed_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_task_ibfk_7` FOREIGN KEY (`snippet_id`) REFERENCES `case_date_based_todo_snippet` (`snippet_id`) ON DELETE SET NULL,
  CONSTRAINT `case_task_ibfk_8` FOREIGN KEY (`due_date_updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `case_task_chk_1` CHECK ((`is_addition` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `change_log`;
CREATE TABLE `change_log` (
  `change_log_id` int NOT NULL AUTO_INCREMENT,
  `date` datetime DEFAULT NULL,
  `modified_by_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `form_id` int DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `email_template_id` int DEFAULT NULL,
  `sms_template_id` int DEFAULT NULL,
  `match_sheet_id` int DEFAULT NULL,
  `profile_template_id` int DEFAULT NULL,
  `date_based_to_do_snippet_template_id` int DEFAULT NULL,
  PRIMARY KEY (`change_log_id`),
  KEY `modified_by_id` (`modified_by_id`),
  KEY `form_id` (`form_id`),
  KEY `template_id` (`template_id`),
  KEY `email_template_id` (`email_template_id`),
  KEY `match_sheet_id` (`match_sheet_id`),
  KEY `profile_template_id` (`profile_template_id`),
  KEY `sms_template_id` (`sms_template_id`),
  KEY `date_based_to_do_snippet_template_id` (`date_based_to_do_snippet_template_id`),
  CONSTRAINT `change_log_ibfk_1` FOREIGN KEY (`modified_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_2` FOREIGN KEY (`form_id`) REFERENCES `form` (`form_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_3` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_4` FOREIGN KEY (`email_template_id`) REFERENCES `email_template` (`email_template_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_5` FOREIGN KEY (`profile_template_id`) REFERENCES `profile_base` (`profile_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_6` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_7` FOREIGN KEY (`match_sheet_id`) REFERENCES `match_sheet_template` (`match_sheet_id`) ON DELETE CASCADE,
  CONSTRAINT `change_log_ibfk_8` FOREIGN KEY (`date_based_to_do_snippet_template_id`) REFERENCES `date_based_todo_snippet_template` (`snippet_template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `chatbot_audit_log`;
CREATE TABLE `chatbot_audit_log` (
  `chatbot_audit_log_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `session_id` varchar(64) DEFAULT NULL,
  `action_type` varchar(64) DEFAULT NULL,
  `data_snapshot` text,
  PRIMARY KEY (`chatbot_audit_log_id`),
  KEY `ix_chatbot_audit_log_contact_created` (`contact_id`,`created`),
  KEY `ix_chatbot_audit_log_session_id` (`session_id`),
  CONSTRAINT `chatbot_audit_log_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `chatbot_event`;
CREATE TABLE `chatbot_event` (
  `chatbot_event_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `case_id` int DEFAULT NULL,
  `case_type` varchar(8) DEFAULT NULL,
  `event_type` varchar(64) DEFAULT NULL,
  `bot_session_id` varchar(64) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `last_signaled_at` datetime DEFAULT NULL,
  `signal_count` int DEFAULT NULL,
  `resolved_at` datetime DEFAULT NULL,
  `resolved_by_admin_id` int DEFAULT NULL,
  `external_alert_id` varchar(64) DEFAULT NULL,
  `alert_tier` varchar(32) DEFAULT NULL,
  `trigger_source` varchar(64) DEFAULT NULL,
  `trigger_details` text,
  `requested_change` text,
  `custom_messaging_ref` text,
  `bot_marked_resolved` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`chatbot_event_id`),
  UNIQUE KEY `ux_chatbot_event_external_alert_id` (`external_alert_id`),
  KEY `resolved_by_admin_id` (`resolved_by_admin_id`),
  KEY `ix_chatbot_event_contact_unresolved` (`contact_id`,`resolved_at`),
  KEY `ix_chatbot_event_resolved_at` (`resolved_at`),
  CONSTRAINT `chatbot_event_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `chatbot_event_ibfk_2` FOREIGN KEY (`resolved_by_admin_id`) REFERENCES `admin` (`admin_id`),
  CONSTRAINT `chatbot_event_chk_1` CHECK ((`bot_marked_resolved` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `clinic`;
CREATE TABLE `clinic` (
  `clinic_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `portal_enabled` tinyint(1) DEFAULT '0',
  `created` datetime DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `street_address_1` varchar(255) DEFAULT NULL,
  `street_address_2` varchar(255) DEFAULT NULL,
  `city` varchar(255) DEFAULT NULL,
  `state` varchar(255) DEFAULT NULL,
  `zip_code` varchar(10) DEFAULT NULL,
  `country` varchar(50) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `fax_number` varchar(25) DEFAULT NULL,
  `email_address` varchar(255) DEFAULT NULL,
  `surro_partner_required_at_screening` tinyint(1) DEFAULT NULL,
  `timeline_for_record_review` varchar(255) DEFAULT NULL,
  `medical_records_contact_name` varchar(255) DEFAULT NULL,
  `gc_age_range` varchar(255) DEFAULT NULL,
  `ivf_liaison_notes` varchar(255) DEFAULT NULL,
  `max_prior_deliveries` varchar(255) DEFAULT NULL,
  `max_prior_csections` varchar(255) DEFAULT NULL,
  `ob_clearance` varchar(255) DEFAULT NULL,
  `hep_b_vaccine` varchar(255) DEFAULT NULL,
  `recent_delivery_timeline` varchar(255) DEFAULT NULL,
  `breastfeeding_timeline` varchar(255) DEFAULT NULL,
  `iud_implanon_policy` varchar(255) DEFAULT NULL,
  `depo_policy` varchar(255) DEFAULT NULL,
  `birth_control_pill_policy` varchar(255) DEFAULT NULL,
  `tattoo_policy` varchar(255) DEFAULT NULL,
  `covid_policy` varchar(255) DEFAULT NULL,
  `additional_criteria` varchar(255) DEFAULT NULL,
  `copy_doctor` tinyint(1) DEFAULT NULL,
  `bmi_range` varchar(255) DEFAULT NULL,
  `donor_cycle_max` varchar(255) DEFAULT NULL,
  `donor_age_range_accepted` varchar(255) DEFAULT NULL,
  `genetic_evaluation` tinyint(1) DEFAULT NULL,
  `pap_smear` tinyint(1) DEFAULT NULL,
  `cohort_meeting_required` varchar(10) DEFAULT NULL,
  `website` varchar(255) DEFAULT NULL,
  `notes` text,
  `relationship_priority` varchar(10) DEFAULT NULL,
  `relationship_summary` varchar(255) DEFAULT NULL,
  `has_fresh_egg_donor` tinyint(1) DEFAULT '0',
  `has_frozen_egg_donor` tinyint(1) DEFAULT '0',
  `being_referred_by_agency` tinyint(1) DEFAULT NULL,
  `has_internal_surrogacy_agency` tinyint(1) DEFAULT '0',
  `monitoring_contact` varchar(255) DEFAULT NULL,
  `method_of_contact` varchar(255) DEFAULT NULL,
  `in_house_lab` varchar(15) DEFAULT NULL,
  `lab_to_use` varchar(255) DEFAULT NULL,
  `gc_max_age` int DEFAULT NULL,
  `monitoring_hours_start` time DEFAULT NULL,
  `monitoring_hours_end` time DEFAULT NULL,
  `weekends` tinyint(1) DEFAULT '0',
  `e2_pricing` varchar(100) DEFAULT NULL,
  `p4_pricing` varchar(100) DEFAULT NULL,
  `hcg_pricing` varchar(100) DEFAULT NULL,
  `u_s_pricing` varchar(100) DEFAULT NULL,
  `saline_pricing` varchar(100) DEFAULT NULL,
  `era_pricing` varchar(100) DEFAULT NULL,
  `additional_fees` varchar(100) DEFAULT NULL,
  `pricing_notes` text,
  `monitoring_notes` text,
  `portal_website` varchar(255) DEFAULT NULL,
  `logo_path` varchar(255) DEFAULT NULL,
  `message` text,
  `button_color` varchar(15) DEFAULT NULL,
  `banner_path` varchar(255) DEFAULT NULL,
  `sign_up_message` text,
  `facebook_pixel_id` varchar(100) DEFAULT NULL,
  `google_analytics_id` varchar(100) DEFAULT NULL,
  `google_tag_manager_id` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`clinic_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `clinic_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `clinic_contact`;
CREATE TABLE `clinic_contact` (
  `clinic_contact_id` int NOT NULL AUTO_INCREMENT,
  `clinic_id` int DEFAULT NULL,
  `created` date DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `extension_number` int DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `email_address` varchar(255) DEFAULT NULL,
  `point_of_contact` varchar(255) DEFAULT NULL,
  `role` varchar(15) DEFAULT NULL,
  `note` text,
  PRIMARY KEY (`clinic_contact_id`),
  KEY `clinic_id` (`clinic_id`),
  CONSTRAINT `clinic_contact_ibfk_1` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `clinic_document`;
CREATE TABLE `clinic_document` (
  `clinic_document_id` int NOT NULL AUTO_INCREMENT,
  `clinic_id` int DEFAULT NULL,
  `title` varchar(100) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `document_type` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`clinic_document_id`),
  KEY `clinic_id` (`clinic_id`),
  CONSTRAINT `clinic_document_ibfk_1` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `clinic_task`;
CREATE TABLE `clinic_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `task_assigned_to_id` int DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT '0',
  `task_title` varchar(255) DEFAULT NULL,
  `task_description` text,
  `must_be_completed_by` date DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `minutes_to_complete` int DEFAULT '60',
  `task_type` varchar(20) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `last_updated_by` int DEFAULT NULL,
  `completed_by_id` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `task_assigned_to_id` (`task_assigned_to_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `clinic_task_ibfk_4` (`last_updated_by`),
  KEY `clinic_task_ibfk_5` (`completed_by_id`),
  CONSTRAINT `clinic_task_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `clinic_task_ibfk_2` FOREIGN KEY (`task_assigned_to_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `clinic_task_ibfk_3` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `clinic_task_ibfk_4` FOREIGN KEY (`last_updated_by`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `clinic_task_ibfk_5` FOREIGN KEY (`completed_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact`;
CREATE TABLE `contact` (
  `contact_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `dq` tinyint(1) DEFAULT '0',
  `invited` tinyint(1) DEFAULT '0',
  `contact_type` varchar(100) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `nickname` varchar(100) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `referral_date` date DEFAULT NULL,
  `street_address` varchar(255) DEFAULT NULL,
  `street_address_2` varchar(255) DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `state` varchar(100) DEFAULT NULL,
  `zip_code` varchar(10) DEFAULT NULL,
  `country` varchar(100) DEFAULT NULL,
  `ethnicity` varchar(50) DEFAULT NULL,
  `height_feet` int DEFAULT NULL,
  `height_inches` decimal(5,2) DEFAULT NULL,
  `eye_color` varchar(30) DEFAULT NULL,
  `hair_color` varchar(30) DEFAULT NULL,
  `race` varchar(40) DEFAULT NULL,
  `religion` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `career` varchar(100) DEFAULT NULL,
  `education` varchar(100) DEFAULT NULL,
  `ivy_league` tinyint(1) DEFAULT NULL,
  `country_raised` varchar(100) DEFAULT NULL,
  `relationship_status` varchar(100) DEFAULT NULL,
  `referral_source` varchar(25) DEFAULT NULL,
  `referral_details` varchar(255) DEFAULT NULL,
  `weight` int DEFAULT NULL,
  `bmi` decimal(5,2) DEFAULT NULL,
  `primary_language` varchar(50) DEFAULT NULL,
  `us_citizen` tinyint(1) DEFAULT NULL,
  `citizenship` varchar(30) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `phone_number` varchar(25) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `rating` int DEFAULT NULL,
  `hep_b_immune` tinyint(1) DEFAULT '0',
  `assigned_to` int DEFAULT NULL,
  `social_security_number` varchar(255) DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `communication_id` varchar(255) DEFAULT NULL,
  `contact_level` varchar(100) DEFAULT NULL,
  `salesforce_contact_id` varchar(50) DEFAULT NULL,
  `salesforce_account_id` varchar(50) DEFAULT NULL,
  `metric_system` tinyint(1) DEFAULT '0',
  `smoke_free` tinyint(1) DEFAULT NULL,
  `gc_profile_approved` datetime DEFAULT NULL,
  `ed_profile_approved` datetime DEFAULT NULL,
  `spam` tinyint(1) DEFAULT '0',
  `sd_profile_approved` datetime DEFAULT NULL,
  `cmv_status` varchar(30) DEFAULT NULL,
  `pregnancy_history_submitted` datetime DEFAULT NULL,
  `mass_email_opt_in` tinyint(1) DEFAULT '1',
  `sms_twilio_opt_status` varchar(15) DEFAULT NULL,
  `sms_jms_opt_status` varchar(15) DEFAULT NULL,
  `text_consent_status` varchar(30) DEFAULT NULL,
  `text_consent_updated` datetime DEFAULT NULL,
  `text_consent_source` varchar(50) DEFAULT NULL,
  `chatbot_disabled_at` datetime DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `phone_invalid` tinyint(1) NOT NULL DEFAULT '0',
  `covid_vaccination_status` varchar(30) DEFAULT NULL,
  `experienced_surrogate` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`contact_id`),
  UNIQUE KEY `email` (`email`),
  KEY `agency_id` (`agency_id`),
  KEY `assigned_to` (`assigned_to`),
  KEY `fk_contact_status` (`status_id`),
  CONSTRAINT `contact_ibfk_1` FOREIGN KEY (`assigned_to`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `contact_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_contact_status` FOREIGN KEY (`status_id`) REFERENCES `status` (`status_id`),
  CONSTRAINT `contact_chk_1` CHECK ((`mass_email_opt_in` in (0,1))),
  CONSTRAINT `contact_chk_2` CHECK ((`phone_invalid` in (0,1))),
  CONSTRAINT `contact_chk_3` CHECK ((`experienced_surrogate` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_agent_settings`;
CREATE TABLE `contact_agent_settings` (
  `contact_agent_settings_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int NOT NULL,
  `agent_key` varchar(32) NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `overridden_at` datetime DEFAULT NULL,
  PRIMARY KEY (`contact_agent_settings_id`),
  UNIQUE KEY `uq_contact_agent_settings_contact_agent` (`contact_id`,`agent_key`),
  CONSTRAINT `contact_agent_settings_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_agent_settings_chk_1` CHECK ((`enabled` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `contact_document`;
CREATE TABLE `contact_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `uploaded_by_id` int DEFAULT NULL,
  `uploaded_by_type` varchar(100) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `document_group` varchar(40) DEFAULT NULL,
  `folder_id` int DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `contact_id` (`contact_id`),
  KEY `agency_id` (`agency_id`),
  KEY `folder_id` (`folder_id`),
  CONSTRAINT `contact_document_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_document_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_document_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `agency_document_folder` (`agency_document_folder_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_email`;
CREATE TABLE `contact_email` (
  `contact_email_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `email_message_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `is_automatic_log` tinyint(1) DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`contact_email_id`),
  KEY `contact_id` (`contact_id`),
  KEY `email_message_id` (`email_message_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `contact_email_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_email_ibfk_2` FOREIGN KEY (`email_message_id`) REFERENCES `email_message` (`email_message_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_email_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`),
  CONSTRAINT `contact_email_chk_1` CHECK ((`is_automatic_log` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_lead`;
CREATE TABLE `contact_lead` (
  `contact_lead_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `created_as_contact` datetime DEFAULT NULL,
  `first_name` varchar(50) DEFAULT NULL,
  `last_name` varchar(50) DEFAULT NULL,
  `lead_type` varchar(10) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `email_key` varchar(10) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `can_call` tinyint(1) DEFAULT NULL,
  `can_leave_message` tinyint(1) DEFAULT NULL,
  `note` text,
  `phone_number` varchar(15) DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `marketing_json` text,
  `recaptcha_submission_id` int DEFAULT NULL,
  PRIMARY KEY (`contact_lead_id`),
  KEY `agency_id` (`agency_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `contact_id` (`contact_id`),
  KEY `recaptcha_submission_id` (`recaptcha_submission_id`),
  CONSTRAINT `contact_lead_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_lead_ibfk_2` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_lead_ibfk_3` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_lead_ibfk_4` FOREIGN KEY (`recaptcha_submission_id`) REFERENCES `recaptcha_submission` (`recaptcha_submission_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_lead_request`;
CREATE TABLE `contact_lead_request` (
  `contact_lead_request_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `contact_lead_id` int DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `request_question` text,
  PRIMARY KEY (`contact_lead_request_id`),
  KEY `contact_lead_id` (`contact_lead_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `contact_lead_request_ibfk_1` FOREIGN KEY (`contact_lead_id`) REFERENCES `contact_lead` (`contact_lead_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_lead_request_ibfk_2` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_lead_request_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `contact_log`;
CREATE TABLE `contact_log` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `log_date` date DEFAULT NULL,
  `log_time` time DEFAULT NULL,
  `log_type` varchar(255) DEFAULT NULL,
  `log_title` varchar(255) DEFAULT NULL,
  `log_description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `contact_id` int DEFAULT NULL,
  `log_outcome` varchar(50) DEFAULT NULL,
  `last_updated_dt` datetime DEFAULT NULL,
  `last_updated_by_id` int DEFAULT NULL,
  `log_subtype` varchar(255) DEFAULT NULL,
  `sender` varchar(255) DEFAULT NULL,
  `recipients` varchar(255) DEFAULT NULL,
  `text_message_id` int DEFAULT NULL,
  PRIMARY KEY (`log_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `contact_id` (`contact_id`),
  KEY `contact_log_ibfk_3` (`last_updated_by_id`),
  KEY `fk_contact_log_text_message_id` (`text_message_id`),
  CONSTRAINT `contact_log_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_log_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_log_ibfk_3` FOREIGN KEY (`last_updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_contact_log_text_message_id` FOREIGN KEY (`text_message_id`) REFERENCES `text_message` (`text_message_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_note`;
CREATE TABLE `contact_note` (
  `note_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `tags` varchar(255) DEFAULT NULL,
  `note` text,
  `contact_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `admins` text,
  `pinned` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`note_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `contact_note_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_note_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contact_task`;
CREATE TABLE `contact_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `task_assigned_to_id` int DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT '0',
  `task_title` varchar(255) DEFAULT NULL,
  `task_description` text,
  `task_status` varchar(30) DEFAULT NULL,
  `must_be_completed_by` date DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `minutes_to_complete` int DEFAULT '60',
  `task_type` varchar(20) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `last_updated_by` int DEFAULT NULL,
  `completed_by_id` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `task_assigned_to_id` (`task_assigned_to_id`),
  KEY `contact_id` (`contact_id`),
  KEY `contact_task_ibfk_4` (`last_updated_by`),
  KEY `contact_task_ibfk_5` (`completed_by_id`),
  CONSTRAINT `contact_task_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_task_ibfk_2` FOREIGN KEY (`task_assigned_to_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `contact_task_ibfk_3` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `contact_task_ibfk_4` FOREIGN KEY (`completed_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `contact_task_ibfk_5` FOREIGN KEY (`last_updated_by`) REFERENCES `admin` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contract`;
CREATE TABLE `contract` (
  `contract_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `updated_by_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `contract_title` varchar(255) DEFAULT NULL,
  `contract` mediumtext,
  PRIMARY KEY (`contract_id`),
  KEY `updated_by_id` (`updated_by_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `contract_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `contract_ibfk_2` FOREIGN KEY (`updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `contract_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `contract_rel`;
CREATE TABLE `contract_rel` (
  `relationship_id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `user_type` varchar(255) DEFAULT NULL,
  `signature_id` text,
  `case_task_id` int DEFAULT NULL,
  `status` varchar(30) DEFAULT NULL,
  `undelivered_bell_at` datetime DEFAULT NULL,
  `undelivered_email_at` datetime DEFAULT NULL,
  PRIMARY KEY (`relationship_id`),
  KEY `parent_id` (`parent_id`),
  CONSTRAINT `contract_rel_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `hellosign` (`hellosign_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `csrf_token`;
CREATE TABLE `csrf_token` (
  `token_id` int NOT NULL AUTO_INCREMENT,
  `date_created` datetime DEFAULT NULL,
  `token` varchar(100) DEFAULT NULL,
  `form_id` int DEFAULT NULL,
  PRIMARY KEY (`token_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `custom_report`;
CREATE TABLE `custom_report` (
  `custom_report_id` int NOT NULL AUTO_INCREMENT,
  `report_title` varchar(255) DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `widget` tinyint(1) DEFAULT '0',
  `date_depricated` datetime DEFAULT NULL,
  `warning` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `hyperlink` varchar(10) DEFAULT NULL,
  `report_headers` text,
  `report_query` text,
  `query_dict` text,
  PRIMARY KEY (`custom_report_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `custom_sub_stage`;
CREATE TABLE `custom_sub_stage` (
  `sub_stage_id` int NOT NULL AUTO_INCREMENT,
  `template_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `base_sub_stage_id` int NOT NULL,
  `ordering` int DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `stage` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`sub_stage_id`),
  KEY `template_id` (`template_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `base_sub_stage_id` (`base_sub_stage_id`),
  CONSTRAINT `custom_sub_stage_ibfk_1` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_sub_stage_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_sub_stage_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_sub_stage_ibfk_4` FOREIGN KEY (`base_sub_stage_id`) REFERENCES `template_sub_stage` (`sub_stage_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `custom_task`;
CREATE TABLE `custom_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `custom_substage_id` int DEFAULT NULL,
  `base_task_id` int NOT NULL,
  `ordering` int DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `completed_by_admin_id` int DEFAULT NULL,
  `completed_by_user_id` int DEFAULT NULL,
  `submitted_for_approval` tinyint(1) DEFAULT NULL,
  `contract_assigned` datetime DEFAULT NULL,
  `contract_id` int DEFAULT NULL,
  `hellosign_request_id` varchar(100) DEFAULT NULL,
  `contract_parent_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `date_depricated` datetime DEFAULT NULL,
  `current_task_version_id` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `custom_substage_id` (`custom_substage_id`),
  KEY `base_task_id` (`base_task_id`),
  KEY `completed_by_admin_id` (`completed_by_admin_id`),
  KEY `completed_by_user_id` (`completed_by_user_id`),
  KEY `contract_id` (`contract_id`),
  KEY `contract_parent_id` (`contract_parent_id`),
  KEY `current_task_version_id` (`current_task_version_id`),
  CONSTRAINT `custom_task_ibfk_1` FOREIGN KEY (`custom_substage_id`) REFERENCES `custom_sub_stage` (`sub_stage_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_task_ibfk_2` FOREIGN KEY (`base_task_id`) REFERENCES `template_task` (`task_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_task_ibfk_3` FOREIGN KEY (`completed_by_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_task_ibfk_4` FOREIGN KEY (`completed_by_user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `custom_task_ibfk_5` FOREIGN KEY (`contract_id`) REFERENCES `case_contract` (`case_contract_id`) ON DELETE SET NULL,
  CONSTRAINT `custom_task_ibfk_6` FOREIGN KEY (`current_task_version_id`) REFERENCES `template_task` (`task_id`) ON DELETE SET NULL,
  CONSTRAINT `custom_task_ibfk_7` FOREIGN KEY (`contract_parent_id`) REFERENCES `hellosign` (`hellosign_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `cycle_calendar_event`;
CREATE TABLE `cycle_calendar_event` (
  `cycle_calendar_event_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `calendar_event_id` int NOT NULL,
  `retrieval_id` int DEFAULT NULL,
  `transfer_id` int DEFAULT NULL,
  `lab_id` int DEFAULT NULL,
  `pregnancy_id` int DEFAULT NULL,
  `delivery_id` int DEFAULT NULL,
  `sd_retrieval_id` int DEFAULT NULL,
  `date_field` varchar(64) NOT NULL,
  PRIMARY KEY (`cycle_calendar_event_id`),
  UNIQUE KEY `uq_cce_event` (`calendar_event_id`),
  UNIQUE KEY `uq_cce_retrieval` (`retrieval_id`,`date_field`),
  UNIQUE KEY `uq_cce_transfer` (`transfer_id`,`date_field`),
  UNIQUE KEY `uq_cce_lab` (`lab_id`,`date_field`),
  UNIQUE KEY `uq_cce_pregnancy` (`pregnancy_id`,`date_field`),
  UNIQUE KEY `uq_cce_delivery` (`delivery_id`,`date_field`),
  UNIQUE KEY `uq_cce_sd_retrieval` (`sd_retrieval_id`,`date_field`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `cycle_calendar_event_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_2` FOREIGN KEY (`calendar_event_id`) REFERENCES `calendar_event` (`calendar_event_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_3` FOREIGN KEY (`retrieval_id`) REFERENCES `retrieval` (`retrieval_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_4` FOREIGN KEY (`transfer_id`) REFERENCES `transfer` (`transfer_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_5` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`lab_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_6` FOREIGN KEY (`pregnancy_id`) REFERENCES `pregnancy` (`pregnancy_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_7` FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`) ON DELETE CASCADE,
  CONSTRAINT `cycle_calendar_event_ibfk_8` FOREIGN KEY (`sd_retrieval_id`) REFERENCES `sd_retrieval` (`sd_retrieval_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `cycle_event_settings`;
CREATE TABLE `cycle_event_settings` (
  `cycle_event_setting_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `cycle_type` enum('Egg Retrieval','Transfer','Monitoring','Pregnancy Details','Delivery Details','Sperm Retrieval') NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `display_name` varchar(255) DEFAULT NULL,
  `attendee_admin_types` json DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `date_field` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`cycle_event_setting_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `cycle_event_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `dashboard_settings`;
CREATE TABLE `dashboard_settings` (
  `dashboard_settings_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `prebuilt_reports` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`dashboard_settings_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `dashboard_settings_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `dashboard_widget`;
CREATE TABLE `dashboard_widget` (
  `dashboard_widget_id` int NOT NULL AUTO_INCREMENT,
  `dashboard_settings_id` int DEFAULT NULL,
  `type` varchar(255) DEFAULT NULL,
  `custom_report_id` int DEFAULT NULL,
  `columns` varchar(10) DEFAULT NULL,
  `widget_order` int DEFAULT NULL,
  PRIMARY KEY (`dashboard_widget_id`),
  KEY `dashboard_settings_id` (`dashboard_settings_id`),
  KEY `custom_report_id` (`custom_report_id`),
  CONSTRAINT `dashboard_widget_ibfk_1` FOREIGN KEY (`custom_report_id`) REFERENCES `custom_report` (`custom_report_id`) ON DELETE CASCADE,
  CONSTRAINT `dashboard_widget_ibfk_2` FOREIGN KEY (`dashboard_settings_id`) REFERENCES `dashboard_settings` (`dashboard_settings_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `date_based_todo_snippet_template`;
CREATE TABLE `date_based_todo_snippet_template` (
  `snippet_template_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `reference_date` varchar(50) DEFAULT NULL,
  `user_type` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`snippet_template_id`),
  CONSTRAINT `date_based_todo_snippet_template_chk_1` CHECK ((`active` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `date_based_todo_template`;
CREATE TABLE `date_based_todo_template` (
  `todo_template_id` int NOT NULL AUTO_INCREMENT,
  `snippet_template_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `assigned_admin_type` varchar(50) DEFAULT NULL,
  `task_title` varchar(255) DEFAULT NULL,
  `task_description` text,
  `send_email` tinyint(1) DEFAULT NULL,
  `type` varchar(50) DEFAULT NULL,
  `due_date_number` int DEFAULT NULL,
  `due_date_interval` varchar(50) DEFAULT NULL,
  `due_date_before_after` varchar(10) DEFAULT NULL,
  `time_to_complete` varchar(30) DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  PRIMARY KEY (`todo_template_id`),
  KEY `snippet_template_id` (`snippet_template_id`),
  CONSTRAINT `date_based_todo_template_ibfk_1` FOREIGN KEY (`snippet_template_id`) REFERENCES `date_based_todo_snippet_template` (`snippet_template_id`) ON DELETE CASCADE,
  CONSTRAINT `date_based_todo_template_chk_1` CHECK ((`active` in (0,1))),
  CONSTRAINT `date_based_todo_template_chk_2` CHECK ((`send_email` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `default_channel`;
CREATE TABLE `default_channel` (
  `channel_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `channel_type` varchar(2) DEFAULT NULL,
  `channel_title` varchar(255) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `channel_description` text,
  `members` text,
  PRIMARY KEY (`channel_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `default_channel_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `delivery`;
CREATE TABLE `delivery` (
  `delivery_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `ed_case_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `delivery_date` date DEFAULT NULL,
  `delivery_time` time DEFAULT NULL,
  `num_days_nicu` varchar(50) DEFAULT NULL,
  `num_babies` int DEFAULT NULL,
  `delivery_type` varchar(10) DEFAULT NULL,
  `baby_name` varchar(100) DEFAULT NULL,
  `baby_weight` varchar(50) DEFAULT NULL,
  `baby_height` varchar(50) DEFAULT NULL,
  `baby_sex` varchar(50) DEFAULT NULL,
  `apgar_score` varchar(50) DEFAULT NULL,
  `discharge_date` date DEFAULT NULL,
  `surrogate_discharge_date` date DEFAULT NULL,
  `deceased_date` date DEFAULT NULL,
  `notes` text,
  `gestational_age_weeks` int DEFAULT NULL,
  `gestational_age_days` int DEFAULT NULL,
  PRIMARY KEY (`delivery_id`),
  KEY `case_id` (`case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `ed_case_id` (`ed_case_id`),
  CONSTRAINT `delivery_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `delivery_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `delivery_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `delivery_ibfk_4` FOREIGN KEY (`ed_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `delivery_baby`;
CREATE TABLE `delivery_baby` (
  `baby_id` int NOT NULL AUTO_INCREMENT,
  `baby_name` varchar(100) DEFAULT NULL,
  `birth_weight` varchar(50) DEFAULT NULL,
  `birth_height` varchar(50) DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `pregnancy_type` varchar(20) DEFAULT NULL,
  `delivery_type` varchar(50) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `weeks_at_delivery` int DEFAULT NULL,
  `profile_delivery_id` int DEFAULT NULL,
  `complications` text,
  `days_at_delivery` int DEFAULT NULL,
  PRIMARY KEY (`baby_id`),
  KEY `profile_delivery_id` (`profile_delivery_id`),
  CONSTRAINT `delivery_baby_ibfk_1` FOREIGN KEY (`profile_delivery_id`) REFERENCES `gc_profile_delivery` (`delivery_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `delivery_baby_history`;
CREATE TABLE `delivery_baby_history` (
  `delivery_baby_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `baby_id` int NOT NULL,
  `delivery_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`delivery_baby_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_delivery_baby_history_baby_created` (`baby_id`,`created`),
  KEY `ix_delivery_baby_history_delivery` (`delivery_id`),
  CONSTRAINT `delivery_baby_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `delivery_baby_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `delivery_baby_history_chk_1` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `display_config`;
CREATE TABLE `display_config` (
  `display_config_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `feature_key` varchar(64) NOT NULL,
  `scope_user_type` varchar(8) DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `item_key` varchar(128) NOT NULL,
  `is_visible` tinyint(1) NOT NULL DEFAULT '1',
  `sort_order` int NOT NULL DEFAULT '0',
  `settings` json DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  PRIMARY KEY (`display_config_id`),
  UNIQUE KEY `uq_display_config_scope_item` (`agency_id`,`feature_key`,`scope_user_type`,`admin_id`,`item_key`),
  KEY `admin_id` (`admin_id`),
  KEY `ix_display_config_lookup` (`agency_id`,`feature_key`,`scope_user_type`,`admin_id`),
  CONSTRAINT `display_config_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `display_config_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `display_config_chk_1` CHECK ((`is_visible` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_education_history`;
CREATE TABLE `ed_education_history` (
  `ed_education_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `education_info_id` int NOT NULL,
  `profile_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ed_education_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_ed_education_history_education_created` (`education_info_id`,`created`),
  CONSTRAINT `ed_education_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_education_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_education_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `ed_education_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_ethnicity_history`;
CREATE TABLE `ed_ethnicity_history` (
  `ed_ethnicity_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `ethnicity_id` int NOT NULL,
  `profile_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ed_ethnicity_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_ed_ethnicity_history_ethnicity_created` (`ethnicity_id`,`created`),
  KEY `ix_ed_ethnicity_history_profile_created` (`profile_id`,`created`),
  CONSTRAINT `ed_ethnicity_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_ethnicity_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_ethnicity_history_chk_1` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_family_member_ethnicity`;
CREATE TABLE `ed_family_member_ethnicity` (
  `family_member_ethnicity_id` int NOT NULL AUTO_INCREMENT,
  `family_member_id` int DEFAULT NULL,
  `ethnicity` varchar(255) DEFAULT NULL,
  `percent` int DEFAULT NULL,
  PRIMARY KEY (`family_member_ethnicity_id`),
  KEY `family_member_id` (`family_member_id`),
  CONSTRAINT `ed_family_member_ethnicity_ibfk_1` FOREIGN KEY (`family_member_id`) REFERENCES `ed_profile_family_member` (`family_member_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_family_member_history`;
CREATE TABLE `ed_family_member_history` (
  `ed_family_member_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `family_member_id` int NOT NULL,
  `profile_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ed_family_member_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_ed_family_member_history_member_created` (`family_member_id`,`created`),
  CONSTRAINT `ed_family_member_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_family_member_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_family_member_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `ed_family_member_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_profile`;
CREATE TABLE `ed_profile` (
  `profile_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `user_submitted` tinyint(1) DEFAULT NULL,
  `birth_country` varchar(50) DEFAULT NULL,
  `birth_state` varchar(20) DEFAULT NULL,
  `current_city` varchar(100) DEFAULT NULL,
  `residency_status` varchar(20) DEFAULT NULL,
  `encrypted_ssn` varchar(255) DEFAULT NULL,
  `current_relationship` int DEFAULT NULL,
  `request_fee` tinyint(1) DEFAULT NULL,
  `request_fee_amount` decimal(8,2) DEFAULT NULL,
  `sexual_orientation` varchar(25) DEFAULT NULL,
  `blood_type` varchar(10) DEFAULT NULL,
  `mobile_phone` varchar(20) DEFAULT NULL,
  `work_phone` varchar(20) DEFAULT NULL,
  `home_phone` varchar(20) DEFAULT NULL,
  `text_message` tinyint(1) DEFAULT NULL,
  `voice_message` tinyint(1) DEFAULT NULL,
  `preferred_phone` varchar(10) DEFAULT NULL,
  `skin_tone` varchar(20) DEFAULT NULL,
  `dominant_hand` varchar(20) DEFAULT NULL,
  `tattoo` tinyint(1) DEFAULT NULL,
  `tattoo_info` varchar(255) DEFAULT NULL,
  `piercings` tinyint(1) DEFAULT NULL,
  `piercings_info` varchar(255) DEFAULT NULL,
  `race_1` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `race_1_percent` int DEFAULT NULL,
  `race_2` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `race_2_percent` int DEFAULT NULL,
  `race_3` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `race_3_percent` int DEFAULT NULL,
  `race_4` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `race_4_percent` int DEFAULT NULL,
  `jewish_parents` varchar(20) DEFAULT NULL,
  `past_donor` tinyint(1) DEFAULT NULL,
  `donation_availability` varchar(20) DEFAULT NULL,
  `willing_cycle_travel` tinyint(1) DEFAULT NULL,
  `willing_to_fly` tinyint(1) DEFAULT NULL,
  `ed_type` varchar(100) DEFAULT NULL,
  `ip_relationship_status` varchar(255) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci DEFAULT NULL,
  `reach_time` text,
  `referred_notes` text,
  `disorders_json` text,
  `donor_summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `frozen_egg_count` int DEFAULT NULL,
  `full_cycle` tinyint(1) DEFAULT '0',
  `frozen_cycle` tinyint(1) DEFAULT '0',
  `bank_cycle` tinyint(1) DEFAULT '0',
  `edit_history` text,
  `frozen_available` datetime DEFAULT NULL,
  `frozen_sperm_available` datetime DEFAULT NULL,
  `frozen_egg_count_manual_override` datetime DEFAULT NULL,
  `frozen_sperm_vials_manual_override` datetime DEFAULT NULL,
  `total_frozen_eggs_calculated` int DEFAULT NULL,
  `total_frozen_sperm_vials_calculated` int DEFAULT NULL,
  `age_at_freeze_current` int DEFAULT NULL,
  PRIMARY KEY (`profile_id`),
  KEY `contact_id` (`contact_id`),
  KEY `ix_ed_profile_frozen_filter` (`frozen_available`,`age_at_freeze_current`),
  KEY `ix_ed_profile_frozen_sperm_filter` (`frozen_sperm_available`,`age_at_freeze_current`),
  CONSTRAINT `ed_profile_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_document`;
CREATE TABLE `ed_profile_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `ed_profile_document_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_education`;
CREATE TABLE `ed_profile_education` (
  `education_info_id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int DEFAULT NULL,
  `education_type` varchar(255) DEFAULT NULL,
  `major` varchar(255) DEFAULT NULL,
  `institution` varchar(100) DEFAULT NULL,
  `marks` varchar(100) DEFAULT NULL,
  `enrollment_year` int DEFAULT NULL,
  `completion_year` int DEFAULT NULL,
  `notes` text,
  `show_institution` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`education_info_id`),
  KEY `profile_id` (`profile_id`),
  CONSTRAINT `ed_profile_education_ibfk_1` FOREIGN KEY (`profile_id`) REFERENCES `ed_profile` (`profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_ethnicity`;
CREATE TABLE `ed_profile_ethnicity` (
  `ethnicity_id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int DEFAULT NULL,
  `ethnicity` varchar(255) DEFAULT NULL,
  `percent` int DEFAULT NULL,
  PRIMARY KEY (`ethnicity_id`),
  KEY `profile_id` (`profile_id`),
  CONSTRAINT `ed_profile_ethnicity_ibfk_1` FOREIGN KEY (`profile_id`) REFERENCES `ed_profile` (`profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_profile_family_member`;
CREATE TABLE `ed_profile_family_member` (
  `family_member_id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int DEFAULT NULL,
  `relation` varchar(30) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `sex` varchar(20) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `eye_color` varchar(20) DEFAULT NULL,
  `skin_tone` varchar(20) DEFAULT NULL,
  `hair_color` varchar(20) DEFAULT NULL,
  `height` varchar(20) DEFAULT NULL,
  `body_type` varchar(20) DEFAULT NULL,
  `occupation` varchar(100) DEFAULT NULL,
  `health_status` varchar(20) DEFAULT NULL,
  `current_living` varchar(5) DEFAULT NULL,
  `age_at_death` varchar(20) DEFAULT NULL,
  `cause_of_death` varchar(255) DEFAULT NULL,
  `delivery_type` varchar(50) DEFAULT NULL,
  `birth_weight` varchar(20) DEFAULT NULL,
  `birth_length` varchar(20) DEFAULT NULL,
  `pregnancy_complications` text,
  `other_details` text,
  `disorders_json` text,
  `have_info` text,
  `age` int DEFAULT NULL,
  PRIMARY KEY (`family_member_id`),
  KEY `profile_id` (`profile_id`),
  CONSTRAINT `ed_profile_family_member_ibfk_1` FOREIGN KEY (`profile_id`) REFERENCES `ed_profile` (`profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_history`;
CREATE TABLE `ed_profile_history` (
  `ed_profile_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `profile_id` int NOT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ed_profile_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_ed_profile_history_profile_created` (`profile_id`,`created`),
  KEY `ix_ed_profile_history_contact_created` (`contact_id`,`created`),
  CONSTRAINT `ed_profile_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_profile_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_profile_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `ed_profile_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ed_profile_image`;
CREATE TABLE `ed_profile_image` (
  `image_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `image_type` varchar(15) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `edited_path` varchar(255) DEFAULT NULL,
  `is_visible` tinyint DEFAULT '1',
  `caption` varchar(100) DEFAULT NULL,
  `order` int DEFAULT '0',
  PRIMARY KEY (`image_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `ed_profile_image_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_test_result`;
CREATE TABLE `ed_profile_test_result` (
  `test_id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int DEFAULT NULL,
  `test_type` varchar(255) DEFAULT NULL,
  `test_year` int DEFAULT NULL,
  `possible_score` varchar(20) DEFAULT NULL,
  `score` varchar(10) DEFAULT NULL,
  `notes` text,
  PRIMARY KEY (`test_id`),
  KEY `profile_id` (`profile_id`),
  CONSTRAINT `ed_profile_test_result_ibfk_1` FOREIGN KEY (`profile_id`) REFERENCES `ed_profile` (`profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_profile_video`;
CREATE TABLE `ed_profile_video` (
  `video_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `video_path` varchar(255) DEFAULT NULL,
  `length` int DEFAULT NULL,
  PRIMARY KEY (`video_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `ed_profile_video_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ed_test_result_history`;
CREATE TABLE `ed_test_result_history` (
  `ed_test_result_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `test_id` int NOT NULL,
  `profile_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ed_test_result_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_ed_test_result_history_test_created` (`test_id`,`created`),
  CONSTRAINT `ed_test_result_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_test_result_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `ed_test_result_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `ed_test_result_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `email`;
CREATE TABLE `email` (
  `email_id` int NOT NULL AUTO_INCREMENT,
  `content` text,
  PRIMARY KEY (`email_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `email_auto_log_request`;
CREATE TABLE `email_auto_log_request` (
  `email_auto_log_request_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `action` varchar(100) DEFAULT NULL,
  `status` int DEFAULT NULL,
  `email_client` varchar(10) DEFAULT NULL,
  `error_details` text,
  PRIMARY KEY (`email_auto_log_request_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `email_auto_log_request_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `email_message`;
CREATE TABLE `email_message` (
  `email_message_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `received` datetime DEFAULT NULL,
  `urgent` tinyint(1) DEFAULT NULL,
  `autogen` tinyint(1) DEFAULT NULL,
  `email_client` varchar(10) CHARACTER SET utf8mb3 DEFAULT NULL,
  `email_id` varchar(255) CHARACTER SET utf8mb3 DEFAULT NULL,
  `subject` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `from_email` varchar(255) CHARACTER SET utf8mb3 DEFAULT NULL,
  `to_emails` text CHARACTER SET utf8mb3,
  `cc_emails` text CHARACTER SET utf8mb3,
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
  `is_automatic_log` tinyint(1) DEFAULT NULL,
  `synced_by_admin_id` int DEFAULT NULL,
  `external_message_id` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `has_attachments` tinyint(1) NOT NULL DEFAULT '0',
  `source_task_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`email_message_id`),
  UNIQUE KEY `ix_email_message_external_message_id` (`external_message_id`),
  KEY `email_message_ibfk_synced_by_admin_id` (`synced_by_admin_id`),
  CONSTRAINT `email_message_ibfk_synced_by_admin_id` FOREIGN KEY (`synced_by_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `email_message_chk_1` CHECK ((`is_automatic_log` in (0,1))),
  CONSTRAINT `email_message_chk_2` CHECK ((`has_attachments` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

DROP TABLE IF EXISTS `email_sync`;
CREATE TABLE `email_sync` (
  `sync_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `token_id` int DEFAULT NULL,
  `force_retry` tinyint(1) NOT NULL DEFAULT '0',
  `created` datetime DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `window_start` datetime DEFAULT NULL,
  `window_end` datetime DEFAULT NULL,
  `disconnection_email_sent` datetime DEFAULT NULL,
  `status` enum('PENDING','ACTIVE','WILL_RETRY','RETRY_PAUSED','DISCONNECTED','ERROR') DEFAULT NULL,
  `sync_type` enum('PERIODIC','HISTORICAL','MANUAL') NOT NULL,
  `total_messages` int DEFAULT NULL,
  `completed_messages` int DEFAULT NULL,
  `first_seen_message_id` varchar(255) DEFAULT NULL,
  `first_seen_message_sent` datetime DEFAULT NULL,
  `last_seen_message_id` varchar(255) DEFAULT NULL,
  `last_seen_message_sent` datetime DEFAULT NULL,
  `attempt` int DEFAULT NULL,
  `error_type` enum('CONFIGURATION','RATE_LIMITED','TOKEN_EXPIRED','API_ERROR','NETWORK_ERROR','NO_TOKEN','UNKNOWN_ERROR') DEFAULT NULL,
  `error_details` text,
  PRIMARY KEY (`sync_id`),
  KEY `token_id` (`token_id`),
  KEY `idx_created` (`created` DESC),
  KEY `idx_email_sync_admin_created` (`admin_id`,`created`),
  CONSTRAINT `email_sync_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `email_sync_ibfk_2` FOREIGN KEY (`token_id`) REFERENCES `oauth_token` (`token_id`) ON DELETE CASCADE,
  CONSTRAINT `email_sync_chk_1` CHECK ((`force_retry` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `email_template`;
CREATE TABLE `email_template` (
  `email_template_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `campaign_template` tinyint(1) DEFAULT '0',
  `title` varchar(255) DEFAULT NULL,
  `last_updated_id` int DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `email_subject` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `email_text` mediumtext,
  `email_status` tinyint(1) DEFAULT NULL,
  `attachment_path` varchar(255) DEFAULT NULL,
  `attachment_title` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`email_template_id`),
  KEY `last_updated_id` (`last_updated_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `email_template_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `email_template_ibfk_2` FOREIGN KEY (`last_updated_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `err`;
CREATE TABLE `err` (
  `error_id` int NOT NULL AUTO_INCREMENT,
  `first_occurred` datetime DEFAULT NULL,
  `last_occurred` datetime DEFAULT NULL,
  `occurrences` int DEFAULT NULL,
  `action` varchar(255) CHARACTER SET utf8mb3 DEFAULT NULL,
  `url` varchar(255) CHARACTER SET utf8mb3 DEFAULT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
  `user_id` int DEFAULT NULL,
  `user_type` varchar(20) CHARACTER SET utf8mb3 DEFAULT NULL,
  `user_agent` varchar(10) CHARACTER SET utf8mb3 DEFAULT NULL,
  PRIMARY KEY (`error_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

DROP TABLE IF EXISTS `err_400`;
CREATE TABLE `err_400` (
  `error_id` int NOT NULL AUTO_INCREMENT,
  `first_occurred` datetime DEFAULT NULL,
  `last_occurred` datetime DEFAULT NULL,
  `url` varchar(255) DEFAULT NULL,
  `err_code` int DEFAULT NULL,
  PRIMARY KEY (`error_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `err_api`;
CREATE TABLE `err_api` (
  `error_id` int NOT NULL AUTO_INCREMENT,
  `first_occurred` datetime DEFAULT NULL,
  `last_occurred` datetime DEFAULT NULL,
  `occurrences` int DEFAULT NULL,
  `action` varchar(255) DEFAULT NULL,
  `url` varchar(255) DEFAULT NULL,
  `content` text,
  `auth_data` text,
  PRIMARY KEY (`error_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `event`;
CREATE TABLE `event` (
  `event_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `event_name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`event_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `event_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `external_user`;
CREATE TABLE `external_user` (
  `external_user_id` int NOT NULL AUTO_INCREMENT,
  `id_name` varchar(100) DEFAULT NULL,
  `company_name` varchar(255) DEFAULT NULL,
  `security_key` varchar(100) DEFAULT NULL,
  `permissions` text,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`external_user_id`),
  UNIQUE KEY `id_name` (`id_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `family`;
CREATE TABLE `family` (
  `family_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `ip_1_id` int DEFAULT NULL,
  `ip_2_id` int DEFAULT NULL,
  `assigned_admin` int DEFAULT NULL,
  `profile_approved` datetime DEFAULT NULL,
  `referral_date` date DEFAULT NULL,
  `referral_source` varchar(25) DEFAULT NULL,
  `referral_details` varchar(255) DEFAULT NULL,
  `notes` text,
  `profile_path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`family_id`),
  KEY `ip_1_id` (`ip_1_id`),
  KEY `ip_2_id` (`ip_2_id`),
  KEY `assigned_admin` (`assigned_admin`),
  CONSTRAINT `family_ibfk_1` FOREIGN KEY (`ip_2_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `family_ibfk_2` FOREIGN KEY (`ip_1_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `family_ibfk_4` FOREIGN KEY (`assigned_admin`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `favorites`;
CREATE TABLE `favorites` (
  `ip_case_id` int NOT NULL,
  `gc_case_id` int NOT NULL,
  `favorited_at` datetime DEFAULT NULL,
  PRIMARY KEY (`ip_case_id`,`gc_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `favorites_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `favorites_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `form`;
CREATE TABLE `form` (
  `form_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `is_intake` tinyint(1) DEFAULT NULL,
  `warning` tinyint(1) DEFAULT '0',
  `form_type` varchar(100) DEFAULT NULL,
  `form_grouping` varchar(50) DEFAULT NULL,
  `display_title` varchar(100) DEFAULT NULL,
  `backend_title` varchar(100) DEFAULT NULL,
  `form_description` text,
  `zoho_code_snippet` text,
  `admin_only` tinyint(1) DEFAULT NULL,
  `facebook_pixel_id` varchar(100) DEFAULT NULL,
  `google_analytics_id` varchar(100) DEFAULT NULL,
  `google_tag_manager_id` varchar(100) DEFAULT NULL,
  `hubspot_code_snippet` text,
  `focus_first_disabled` tinyint(1) DEFAULT '0',
  `is_prebuilt` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`form_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `form_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `form_change_history`;
CREATE TABLE `form_change_history` (
  `form_change_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `user_form_answer_id` int NOT NULL,
  `admin_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `value` text,
  `answer_type` varchar(50) DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`form_change_history_id`),
  KEY `admin_id` (`admin_id`),
  KEY `contact_id` (`contact_id`),
  KEY `ix_form_change_history_answer_created` (`user_form_answer_id`,`created`),
  CONSTRAINT `form_change_history_ibfk_1` FOREIGN KEY (`user_form_answer_id`) REFERENCES `user_form_answer` (`user_form_question_id`) ON DELETE CASCADE,
  CONSTRAINT `form_change_history_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `form_change_history_ibfk_3` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `form_change_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `form_change_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `form_question`;
CREATE TABLE `form_question` (
  `form_question_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `date_depricated` datetime DEFAULT NULL,
  `depricated_by_id` int DEFAULT NULL,
  `form_id` int DEFAULT NULL,
  `mapped_table` varchar(255) DEFAULT NULL,
  `question_code` varchar(255) DEFAULT NULL,
  `profile_question_id` int DEFAULT NULL,
  `question_type` varchar(255) DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `form_group` varchar(255) DEFAULT NULL,
  `form_group_order` int DEFAULT NULL,
  `required` tinyint(1) DEFAULT NULL,
  `dependent_question_id` int DEFAULT NULL,
  `dependent_answer` text,
  `allows_other` tinyint(1) DEFAULT NULL,
  `rejection_answer` varchar(255) DEFAULT NULL,
  `question` text,
  `answer_options` text,
  `rejection_notification` text,
  `admin_only` tinyint(1) DEFAULT NULL,
  `map_to_form` tinyint(1) DEFAULT '0',
  `mapped_form_id` int DEFAULT NULL,
  `mapped_form_question_id` int DEFAULT NULL,
  `duplicatable` tinyint(1) DEFAULT '0',
  `marketing` tinyint(1) DEFAULT '0',
  `last_updated` datetime DEFAULT NULL,
  PRIMARY KEY (`form_question_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `depricated_by_id` (`depricated_by_id`),
  KEY `form_id` (`form_id`),
  KEY `dependent_question_id` (`dependent_question_id`),
  CONSTRAINT `form_question_ibfk_1` FOREIGN KEY (`depricated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `form_question_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `form_question_ibfk_3` FOREIGN KEY (`form_id`) REFERENCES `form` (`form_id`) ON DELETE CASCADE,
  CONSTRAINT `form_question_ibfk_4` FOREIGN KEY (`dependent_question_id`) REFERENCES `form_question` (`form_question_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `form_question_report`;
CREATE TABLE `form_question_report` (
  `form_question_report_id` int NOT NULL AUTO_INCREMENT,
  `report_title` varchar(100) DEFAULT NULL,
  `report_id` varchar(100) DEFAULT NULL,
  `num_of_form_questions` int DEFAULT NULL,
  `form_question_ids` text,
  `description` text,
  PRIMARY KEY (`form_question_report_id`),
  UNIQUE KEY `report_id` (`report_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `gc_case`;
CREATE TABLE `gc_case` (
  `case_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `case_lock` tinyint(1) DEFAULT '0',
  `confidential` tinyint(1) DEFAULT '0',
  `sign_on_date` date DEFAULT NULL,
  `case_file_name` varchar(255) DEFAULT NULL,
  `gc_id` int DEFAULT NULL,
  `transfer_type` varchar(15) DEFAULT NULL,
  `program_id` int DEFAULT NULL,
  `service_level_id` int DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `case_type` varchar(50) DEFAULT NULL,
  `assigned_admin` int DEFAULT NULL,
  `stage` varchar(50) DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `archive_reason_id` int DEFAULT NULL,
  `donor_status` varchar(50) DEFAULT 'available',
  `case_campaign_id` int DEFAULT NULL,
  `seedtrust_case_id` int DEFAULT NULL,
  `projected_match` datetime DEFAULT NULL,
  `availability` varchar(50) DEFAULT NULL,
  `sperm_source_accept` varchar(20) DEFAULT NULL,
  `open_for_twins` tinyint(1) DEFAULT NULL,
  `pumping_breast_milk` tinyint(1) DEFAULT NULL,
  `prior_gc` tinyint(1) DEFAULT NULL,
  `rematch_journey` tinyint(1) DEFAULT '0',
  `share_seedtrust_details` tinyint(1) DEFAULT '1',
  `num_surros` int DEFAULT NULL,
  `num_children` int DEFAULT NULL,
  `medically_cleared` tinyint(1) DEFAULT NULL,
  `friendly_insurance` tinyint(1) DEFAULT NULL,
  `legally_cleared` tinyint(1) DEFAULT NULL,
  `base_fee` varchar(30) DEFAULT NULL,
  `orientation` varchar(20) DEFAULT NULL,
  `location` varchar(30) DEFAULT NULL,
  `marital_status` varchar(30) DEFAULT NULL,
  `insurance` varchar(255) DEFAULT NULL,
  `birth_control` varchar(255) DEFAULT NULL,
  `match_notes` text,
  `hiv_issue` tinyint(1) DEFAULT NULL,
  `hep_b_issue` tinyint(1) DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `ed_display_anonymous` tinyint(1) DEFAULT '0',
  `cycle_in` varchar(15) DEFAULT NULL,
  `clinic_preapproval` tinyint(1) DEFAULT NULL,
  `num_csections` int DEFAULT NULL,
  `queue_lock` tinyint(1) DEFAULT '0',
  `is_friends_family` tinyint(1) DEFAULT '0',
  `is_private` tinyint(1) DEFAULT '0',
  `journey_number` int DEFAULT NULL,
  `closed` datetime DEFAULT NULL,
  `gurgle_group_id` int DEFAULT NULL,
  `covid_vaccination_status` varchar(255) DEFAULT NULL,
  `display_in_portal` tinyint(1) DEFAULT '1',
  `egg_donor_source_accept` varchar(20) DEFAULT NULL,
  `sd_display_anonymous` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`case_id`),
  KEY `gc_id` (`gc_id`),
  KEY `assigned_admin` (`assigned_admin`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_ibfk_2` (`agency_id`),
  KEY `status_id` (`status_id`),
  KEY `archive_reason_id` (`archive_reason_id`),
  KEY `template_id` (`template_id`),
  KEY `case_campaign_id` (`case_campaign_id`),
  KEY `program_id` (`program_id`),
  KEY `service_level_id` (`service_level_id`),
  CONSTRAINT `gc_case_ibfk_1` FOREIGN KEY (`gc_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `gc_case_ibfk_10` FOREIGN KEY (`archive_reason_id`) REFERENCES `archive_reason` (`archive_reason_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `gc_case_ibfk_3` FOREIGN KEY (`assigned_admin`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_4` FOREIGN KEY (`status_id`) REFERENCES `status` (`status_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_5` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_6` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`),
  CONSTRAINT `gc_case_ibfk_7` FOREIGN KEY (`case_campaign_id`) REFERENCES `case_campaign` (`case_campaign_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_8` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_ibfk_9` FOREIGN KEY (`service_level_id`) REFERENCES `service_level` (`service_level_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_case_chk_1` CHECK ((`sd_display_anonymous` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `gc_profile_delivery`;
CREATE TABLE `gc_profile_delivery` (
  `delivery_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `pregnancy_type` varchar(20) DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `was_surrogate` tinyint(1) DEFAULT NULL,
  `display_complications` tinyint(1) DEFAULT '0',
  `multiple_birth` smallint DEFAULT NULL,
  `delivery_type` varchar(100) DEFAULT NULL,
  `birth_weight` varchar(50) DEFAULT NULL,
  `weeks_to_conceive` int DEFAULT NULL,
  `weeks_at_delivery` int DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `complications` text,
  `period_of_miscarriage` varchar(100) DEFAULT NULL,
  `period_of_stillbirth` varchar(100) DEFAULT NULL,
  `period_of_termination` varchar(100) DEFAULT NULL,
  `dc_or_de_performed` tinyint(1) DEFAULT NULL,
  `was_termination_elective` varchar(255) DEFAULT NULL,
  `is_draft` datetime DEFAULT NULL,
  `days_at_delivery` int DEFAULT NULL,
  PRIMARY KEY (`delivery_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `gc_profile_delivery_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `gc_profile_delivery_history`;
CREATE TABLE `gc_profile_delivery_history` (
  `gc_profile_delivery_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `delivery_id` int NOT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`gc_profile_delivery_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_gc_profile_delivery_history_delivery_created` (`delivery_id`,`created`),
  KEY `ix_gc_profile_delivery_history_contact` (`contact_id`),
  CONSTRAINT `gc_profile_delivery_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_profile_delivery_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `gc_profile_delivery_history_chk_1` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `gc_profile_document`;
CREATE TABLE `gc_profile_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `gc_profile_document_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `gc_profile_image`;
CREATE TABLE `gc_profile_image` (
  `image_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `image_type` varchar(15) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `edited_path` varchar(255) DEFAULT NULL,
  `is_visible` tinyint DEFAULT '1',
  `caption` varchar(100) DEFAULT NULL,
  `order` int DEFAULT '0',
  PRIMARY KEY (`image_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `gc_profile_image_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `gc_profile_video`;
CREATE TABLE `gc_profile_video` (
  `video_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `video_path` varchar(255) DEFAULT NULL,
  `length` int DEFAULT NULL,
  PRIMARY KEY (`video_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `gc_profile_video_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `general_form_submission`;
CREATE TABLE `general_form_submission` (
  `general_form_submission_id` int NOT NULL AUTO_INCREMENT,
  `form_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `created` datetime DEFAULT CURRENT_TIMESTAMP,
  `browser` varchar(255) DEFAULT NULL,
  `form_data` mediumtext,
  `has_files` tinyint DEFAULT NULL,
  PRIMARY KEY (`general_form_submission_id`),
  KEY `form_id` (`form_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `general_form_submission_ibfk_1` FOREIGN KEY (`form_id`) REFERENCES `form` (`form_id`) ON DELETE SET NULL,
  CONSTRAINT `general_form_submission_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `general_task`;
CREATE TABLE `general_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `task_assigned_to_id` int DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT NULL,
  `task_title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `task_status` varchar(30) DEFAULT NULL,
  `task_description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
  `must_be_completed_by` date DEFAULT NULL,
  `must_be_completed_time` time DEFAULT NULL,
  `minutes_to_complete` int DEFAULT NULL,
  `task_type` varchar(20) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `group_id` varchar(100) DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `task_repeat` varchar(10) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `last_updated_by` int DEFAULT NULL,
  `completed_by_id` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `completed_by_id` (`completed_by_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `last_updated_by` (`last_updated_by`),
  KEY `task_assigned_to_id` (`task_assigned_to_id`),
  CONSTRAINT `general_task_ibfk_1` FOREIGN KEY (`completed_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `general_task_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `general_task_ibfk_3` FOREIGN KEY (`last_updated_by`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `general_task_ibfk_4` FOREIGN KEY (`task_assigned_to_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `general_task_chk_1` CHECK ((`flagged` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `gurgle_token`;
CREATE TABLE `gurgle_token` (
  `gurgle_token_id` int NOT NULL,
  `access_key` varchar(255) DEFAULT NULL,
  `refresh_token` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`gurgle_token_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS `hellosign`;
CREATE TABLE `hellosign` (
  `hellosign_id` int NOT NULL AUTO_INCREMENT,
  `signature_request_id` varchar(255) DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  PRIMARY KEY (`hellosign_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `hellosign_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `hellosign_template`;
CREATE TABLE `hellosign_template` (
  `template_record_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `template_id` text,
  `template_title` varchar(255) DEFAULT NULL,
  `template_type` varchar(10) DEFAULT NULL,
  `doc_path` text,
  PRIMARY KEY (`template_record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `intake_form_submission`;
CREATE TABLE `intake_form_submission` (
  `intake_form_submission_id` int NOT NULL AUTO_INCREMENT,
  `intake_form_id` int DEFAULT NULL,
  `created` datetime DEFAULT CURRENT_TIMESTAMP,
  `browser` varchar(255) DEFAULT NULL,
  `form_data` text,
  `recaptcha_submission_id` int DEFAULT NULL,
  `failed_validation` tinyint(1) DEFAULT NULL,
  `validation_errors` text,
  PRIMARY KEY (`intake_form_submission_id`),
  KEY `intake_form_id` (`intake_form_id`),
  KEY `recaptcha_submission_id` (`recaptcha_submission_id`),
  CONSTRAINT `intake_form_submission_ibfk_1` FOREIGN KEY (`intake_form_id`) REFERENCES `form` (`form_id`) ON DELETE SET NULL,
  CONSTRAINT `intake_form_submission_ibfk_2` FOREIGN KEY (`recaptcha_submission_id`) REFERENCES `recaptcha_submission` (`recaptcha_submission_id`) ON DELETE SET NULL,
  CONSTRAINT `intake_form_submission_chk_1` CHECK ((`failed_validation` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ip_address`;
CREATE TABLE `ip_address` (
  `ip_address_id` int NOT NULL AUTO_INCREMENT,
  `ip_address` varchar(32) DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `user_type` varchar(20) DEFAULT NULL,
  `user_agent` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ip_address_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ip_address_err`;
CREATE TABLE `ip_address_err` (
  `ip_address_id` int NOT NULL,
  `error_id` int NOT NULL,
  `occurances` int DEFAULT NULL,
  PRIMARY KEY (`ip_address_id`,`error_id`),
  KEY `error_id` (`error_id`),
  CONSTRAINT `ip_address_err_ibfk_1` FOREIGN KEY (`ip_address_id`) REFERENCES `ip_address` (`ip_address_id`) ON DELETE CASCADE,
  CONSTRAINT `ip_address_err_ibfk_2` FOREIGN KEY (`error_id`) REFERENCES `err_400` (`error_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `ip_case`;
CREATE TABLE `ip_case` (
  `case_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `family_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `ed_case_id` int DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `case_lock` tinyint(1) DEFAULT '0',
  `confidential` tinyint(1) DEFAULT '0',
  `show_ed_list` tinyint(1) DEFAULT NULL,
  `sign_on_date` date DEFAULT NULL,
  `case_file_name` varchar(255) DEFAULT NULL,
  `stage` varchar(50) DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `ed_status_id` int DEFAULT NULL,
  `archive_reason_id` int DEFAULT NULL,
  `assigned_admin` int DEFAULT NULL,
  `case_campaign_id` int DEFAULT NULL,
  `completed` datetime DEFAULT NULL,
  `financially_cleared` tinyint(1) DEFAULT NULL,
  `medically_cleared` tinyint(1) DEFAULT NULL,
  `legally_cleared` tinyint(1) DEFAULT NULL,
  `seedtrust_case_id` int DEFAULT NULL,
  `num_of_babies` int DEFAULT NULL,
  `transfer_type` varchar(10) DEFAULT NULL,
  `program_id` int DEFAULT NULL,
  `service_level_id` int DEFAULT NULL,
  `matching_type` varchar(10) DEFAULT NULL,
  `can_queue_donors` tinyint(1) DEFAULT '0',
  `orientation` varchar(20) DEFAULT NULL,
  `location` varchar(30) DEFAULT NULL,
  `marital_status` varchar(30) DEFAULT NULL,
  `child_citizenship` varchar(255) DEFAULT NULL,
  `match_notes` text,
  `spar` tinyint(1) DEFAULT NULL,
  `hepatitis_b` tinyint(1) DEFAULT NULL,
  `rematch_journey` tinyint(1) DEFAULT '0',
  `share_seedtrust_details` tinyint(1) DEFAULT '1',
  `projected_match` datetime DEFAULT NULL,
  `egg_source` varchar(50) DEFAULT NULL,
  `sperm_source` varchar(20) DEFAULT NULL,
  `embryo_creation_status` varchar(50) DEFAULT NULL,
  `level_of_english` varchar(15) DEFAULT NULL,
  `consult_date` date DEFAULT NULL,
  `journey_number` int DEFAULT NULL,
  `access_private` tinyint(1) DEFAULT '0',
  `closed` datetime DEFAULT NULL,
  `stripe_payment_id` varchar(255) DEFAULT NULL,
  `ed_stripe_payment_id` varchar(255) DEFAULT NULL,
  `pregnancy_tracker_details` varchar(255) DEFAULT NULL,
  `first_day_latest_period` date DEFAULT NULL,
  `probable_ovulation_date` date DEFAULT NULL,
  `latest_period_length` int DEFAULT NULL,
  `menstrual_cycle_length` int DEFAULT NULL,
  `gurgle_group_id` int DEFAULT NULL,
  `sd_status_id` int DEFAULT NULL,
  `sd_case_id` int DEFAULT NULL,
  `show_sd_list` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`case_id`),
  KEY `family_id` (`family_id`),
  KEY `assigned_admin` (`assigned_admin`),
  KEY `program_id` (`program_id`),
  KEY `ip_case_ibfk_1` (`agency_id`),
  KEY `status_id` (`status_id`),
  KEY `ed_status_id` (`ed_status_id`),
  KEY `archive_reason_id` (`archive_reason_id`),
  KEY `ed_case_id` (`ed_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `case_campaign_id` (`case_campaign_id`),
  KEY `service_level_id` (`service_level_id`),
  KEY `template_id` (`template_id`),
  KEY `sd_status_id` (`sd_status_id`),
  KEY `sd_case_id` (`sd_case_id`),
  CONSTRAINT `ip_case_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `ip_case_ibfk_10` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_11` FOREIGN KEY (`archive_reason_id`) REFERENCES `archive_reason` (`archive_reason_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_12` FOREIGN KEY (`case_campaign_id`) REFERENCES `case_campaign` (`case_campaign_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_13` FOREIGN KEY (`service_level_id`) REFERENCES `service_level` (`service_level_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_14` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_15` FOREIGN KEY (`ed_status_id`) REFERENCES `status` (`status_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_16` FOREIGN KEY (`sd_status_id`) REFERENCES `status` (`status_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_17` FOREIGN KEY (`sd_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_2` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_6` FOREIGN KEY (`assigned_admin`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_7` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_8` FOREIGN KEY (`ed_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_ibfk_9` FOREIGN KEY (`status_id`) REFERENCES `status` (`status_id`) ON DELETE SET NULL,
  CONSTRAINT `ip_case_chk_1` CHECK ((`show_sd_list` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ip_profile_document`;
CREATE TABLE `ip_profile_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `family_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `family_id` (`family_id`),
  CONSTRAINT `ip_profile_document_ibfk_1` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ip_profile_image`;
CREATE TABLE `ip_profile_image` (
  `image_id` int NOT NULL AUTO_INCREMENT,
  `family_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `image_type` varchar(15) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `edited_path` varchar(255) DEFAULT NULL,
  `is_visible` tinyint DEFAULT '1',
  `caption` varchar(100) DEFAULT NULL,
  `order` int DEFAULT '0',
  PRIMARY KEY (`image_id`),
  KEY `family_id` (`family_id`),
  CONSTRAINT `ip_profile_image_ibfk_1` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ip_profile_video`;
CREATE TABLE `ip_profile_video` (
  `video_id` int NOT NULL AUTO_INCREMENT,
  `family_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `video_path` varchar(255) DEFAULT NULL,
  `length` int DEFAULT NULL,
  PRIMARY KEY (`video_id`),
  KEY `family_id` (`family_id`),
  CONSTRAINT `ip_profile_video_ibfk_1` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `ip_rep`;
CREATE TABLE `ip_rep` (
  `ip_case_id` int NOT NULL,
  `contact_id` int NOT NULL,
  PRIMARY KEY (`ip_case_id`,`contact_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `ip_rep_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `ip_rep_ibfk_2` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `journey_photo`;
CREATE TABLE `journey_photo` (
  `journey_photo_id` int NOT NULL AUTO_INCREMENT,
  `uploaded` datetime DEFAULT NULL,
  `caption` varchar(140) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `viewable_by` varchar(255) DEFAULT NULL,
  `uploaded_by_id` int DEFAULT NULL,
  `uploaded_by_type` varchar(20) DEFAULT NULL,
  `is_visible` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`journey_photo_id`),
  KEY `ip_case_id` (`ip_case_id`),
  CONSTRAINT `journey_photo_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `lab`;
CREATE TABLE `lab` (
  `lab_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `ed_case_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `event_id` int DEFAULT NULL,
  `date_labs_drawn` datetime DEFAULT NULL,
  `time_labs_drawn` time DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `clinic_name` varchar(255) DEFAULT NULL,
  `days_last_transfer` varchar(100) DEFAULT NULL,
  `result` text,
  `notes` text,
  PRIMARY KEY (`lab_id`),
  KEY `case_id` (`case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `ed_case_id` (`ed_case_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `event_id` (`event_id`),
  CONSTRAINT `lab_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `lab_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `lab_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `lab_ibfk_4` FOREIGN KEY (`ed_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `lab_ibfk_5` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `lab_ibfk_6` FOREIGN KEY (`event_id`) REFERENCES `event` (`event_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `mass_email`;
CREATE TABLE `mass_email` (
  `mass_email_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `email_target` varchar(255) DEFAULT NULL,
  `stage` varchar(255) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `to_emails` text,
  `attachment_path` varchar(255) DEFAULT NULL,
  `attachment_name` varchar(255) DEFAULT NULL,
  `content` text,
  `ip_ed_status` varchar(255) DEFAULT NULL,
  `ip_sd_status` varchar(255) DEFAULT NULL,
  `to_contact_ids` text,
  PRIMARY KEY (`mass_email_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `mass_email_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `mass_send_recipient`;
CREATE TABLE `mass_send_recipient` (
  `mass_send_recipient_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `source` varchar(30) NOT NULL,
  `source_id` int NOT NULL,
  `contact_id` int DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `status` enum('SENT','FAILED') NOT NULL,
  `failure_reason` varchar(30) DEFAULT NULL,
  `text_message_id` int DEFAULT NULL,
  PRIMARY KEY (`mass_send_recipient_id`),
  KEY `contact_id` (`contact_id`),
  KEY `text_message_id` (`text_message_id`),
  KEY `ix_mass_send_recipient_source` (`source`,`source_id`),
  CONSTRAINT `mass_send_recipient_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `mass_send_recipient_ibfk_2` FOREIGN KEY (`text_message_id`) REFERENCES `text_message` (`text_message_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `mass_text`;
CREATE TABLE `mass_text` (
  `mass_text_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `body` text,
  `sms_template_id` int DEFAULT NULL,
  `text_target` varchar(255) DEFAULT NULL,
  `stage` varchar(255) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `ip_ed_status` varchar(255) DEFAULT NULL,
  `ip_sd_status` varchar(255) DEFAULT NULL,
  `to_phones` text,
  `sent_count` int DEFAULT NULL,
  `failed_count` int DEFAULT NULL,
  `send_status` enum('PENDING','SENDING','COMPLETED','FAILED') NOT NULL,
  `to_contact_ids` text,
  PRIMARY KEY (`mass_text_id`),
  KEY `admin_id` (`admin_id`),
  KEY `sms_template_id` (`sms_template_id`),
  CONSTRAINT `mass_text_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `mass_text_ibfk_2` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `match_break_details`;
CREATE TABLE `match_break_details` (
  `match_break_detail_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `matching_queue_id` int DEFAULT NULL,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `break_reason` varchar(100) DEFAULT NULL,
  `break_notes` varchar(255) DEFAULT NULL,
  `num_of_transfers` varchar(50) DEFAULT NULL,
  `gc_rematch_possible` varchar(10) DEFAULT NULL,
  `need_new_gc_match` varchar(10) DEFAULT NULL,
  `prior_retrieval_completed` varchar(10) DEFAULT NULL,
  `ed_rematch_possible` varchar(10) DEFAULT NULL,
  `need_new_ed_match` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`match_break_detail_id`),
  KEY `matching_queue_id` (`matching_queue_id`),
  KEY `case_id` (`case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `match_break_details_ibfk_1` FOREIGN KEY (`matching_queue_id`) REFERENCES `matching_queue` (`matching_queue_id`) ON DELETE CASCADE,
  CONSTRAINT `match_break_details_ibfk_2` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `match_break_details_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `match_sheet_header`;
CREATE TABLE `match_sheet_header` (
  `header_id` int NOT NULL AUTO_INCREMENT,
  `match_sheet_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `grid_size` int DEFAULT NULL,
  `section_order` int NOT NULL,
  `header_order` int NOT NULL,
  `section_name` varchar(50) NOT NULL,
  `header_name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`header_id`),
  KEY `match_sheet_id` (`match_sheet_id`),
  CONSTRAINT `match_sheet_header_ibfk_1` FOREIGN KEY (`match_sheet_id`) REFERENCES `match_sheet_template` (`match_sheet_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `match_sheet_question`;
CREATE TABLE `match_sheet_question` (
  `question_id` int NOT NULL AUTO_INCREMENT,
  `header_id` int NOT NULL,
  `mapped_form_question_id` int DEFAULT NULL,
  `mapped_sheet_question_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `question_order` int NOT NULL,
  `mapped_table` varchar(11) DEFAULT NULL,
  `mapped_column` varchar(40) DEFAULT NULL,
  `question_type` varchar(50) DEFAULT NULL,
  `question_text` text,
  `answer_options` text,
  PRIMARY KEY (`question_id`),
  KEY `header_id` (`header_id`),
  KEY `mapped_form_question_id` (`mapped_form_question_id`),
  KEY `mapped_sheet_question_id` (`mapped_sheet_question_id`),
  CONSTRAINT `match_sheet_question_ibfk_1` FOREIGN KEY (`header_id`) REFERENCES `match_sheet_header` (`header_id`) ON DELETE CASCADE,
  CONSTRAINT `match_sheet_question_ibfk_2` FOREIGN KEY (`mapped_form_question_id`) REFERENCES `form_question` (`form_question_id`) ON DELETE SET NULL,
  CONSTRAINT `match_sheet_question_ibfk_3` FOREIGN KEY (`mapped_sheet_question_id`) REFERENCES `match_sheet_question` (`question_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `match_sheet_template`;
CREATE TABLE `match_sheet_template` (
  `match_sheet_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `title` varchar(100) DEFAULT NULL,
  `description` text,
  PRIMARY KEY (`match_sheet_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `match_sheet_template_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `matching_days_report`;
CREATE TABLE `matching_days_report` (
  `matching_days_report_id` int NOT NULL AUTO_INCREMENT,
  `ip_case_id` int DEFAULT NULL,
  `move_to_matching` datetime DEFAULT NULL,
  `match_fully_approved` datetime DEFAULT NULL,
  PRIMARY KEY (`matching_days_report_id`),
  KEY `ip_case_id` (`ip_case_id`),
  CONSTRAINT `matching_days_report_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `matching_filter_preferences`;
CREATE TABLE `matching_filter_preferences` (
  `matching_filter_preferences_id` int NOT NULL AUTO_INCREMENT,
  `donors` text,
  `surrogates` text,
  `intended_parents` text,
  `sperm_donors` text,
  PRIMARY KEY (`matching_filter_preferences_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `matching_preferences`;
CREATE TABLE `matching_preferences` (
  `preference_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `age_min` int DEFAULT NULL,
  `age_max` int DEFAULT NULL,
  `bmi_min` int DEFAULT NULL,
  `bmi_max` int DEFAULT NULL,
  `ed_type` varchar(50) DEFAULT NULL,
  `ip_relationship_status` varchar(255) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci DEFAULT NULL,
  `termination` varchar(255) DEFAULT NULL,
  `num_children_min` tinyint DEFAULT NULL,
  `num_children_max` tinyint DEFAULT NULL,
  `prior_surrogate` tinyint(1) DEFAULT NULL,
  `prior_surrogate_min` tinyint DEFAULT NULL,
  `prior_surrogate_max` tinyint DEFAULT NULL,
  `selective_reduction` tinyint(1) DEFAULT NULL,
  `marital_status` varchar(50) DEFAULT NULL,
  `base_fee` decimal(8,2) DEFAULT NULL,
  `higher_base_fee` tinyint(1) DEFAULT NULL,
  `friendly_insurance` tinyint(1) DEFAULT NULL,
  `transfer_type` varchar(10) DEFAULT NULL,
  `race` varchar(255) DEFAULT NULL,
  `ethnicity` varchar(255) DEFAULT NULL,
  `height_min` int DEFAULT NULL,
  `height_max` int DEFAULT NULL,
  `city` varchar(255) DEFAULT NULL,
  `state` varchar(255) DEFAULT NULL,
  `country` varchar(255) DEFAULT NULL,
  `religion` varchar(255) DEFAULT NULL,
  `hair_color` varchar(25) DEFAULT NULL,
  `eye_color` varchar(25) DEFAULT NULL,
  `hep_b_immune` tinyint(1) DEFAULT NULL,
  `orientation` varchar(255) DEFAULT NULL,
  `twins` tinyint(1) DEFAULT NULL,
  `pbo` tinyint(1) DEFAULT '0',
  `availability` varchar(255) DEFAULT NULL,
  `smoke_free` tinyint(1) DEFAULT NULL,
  `num_csections` int DEFAULT NULL,
  `out_of_state_ip` tinyint(1) DEFAULT NULL,
  `international_ip` tinyint(1) DEFAULT NULL,
  `ip_using_translator` tinyint(1) DEFAULT NULL,
  `ip_children` tinyint(1) DEFAULT NULL,
  `travel_appointment` tinyint(1) DEFAULT NULL,
  `single_parent_male` tinyint(1) DEFAULT NULL,
  `single_parent_female` tinyint(1) DEFAULT NULL,
  `same_sex_ip` tinyint(1) DEFAULT NULL,
  `same_sex_couples` tinyint(1) DEFAULT NULL,
  `vaccinations` tinyint(1) DEFAULT NULL,
  `permanent_residence` tinyint(1) DEFAULT NULL,
  `family_delivery` tinyint(1) DEFAULT NULL,
  `hiv` tinyint(1) DEFAULT NULL,
  `matching_type` varchar(10) DEFAULT NULL,
  `notes` text,
  `age_at_freeze_min` int DEFAULT NULL,
  `age_at_freeze_max` int DEFAULT NULL,
  `frozen_available` tinyint(1) DEFAULT NULL,
  `covid_vaccination_status` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`preference_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `matching_preferences_ibfk_1` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `matching_preferences_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `matching_preferences_chk_1` CHECK ((`frozen_available` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `matching_queue`;
CREATE TABLE `matching_queue` (
  `matching_queue_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `send_type` varchar(10) DEFAULT NULL,
  `ip_approve` tinyint(1) DEFAULT NULL,
  `gc_approve` tinyint(1) DEFAULT NULL,
  `ip_decision_by_admin` tinyint(1) DEFAULT '0',
  `gc_decision_by_admin` tinyint(1) DEFAULT '0',
  `ip_sent_date` datetime DEFAULT NULL,
  `gc_sent_date` datetime DEFAULT NULL,
  `match_accepted` datetime DEFAULT NULL,
  `match_break` datetime DEFAULT NULL,
  `ip_notes` text,
  `gc_notes` text,
  `sent_by_id` int DEFAULT NULL,
  `sent_by_type` varchar(25) DEFAULT NULL,
  `donation_type` varchar(10) DEFAULT NULL,
  `matching_type` varchar(25) DEFAULT NULL,
  `case_coordinator_notes` text,
  `admin_ip_notes` text,
  `admin_gc_notes` text,
  `admin_ed_notes` text,
  `archive_reason` text,
  PRIMARY KEY (`matching_queue_id`),
  KEY `case_id` (`case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `matching_queue_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `matching_queue_ibfk_4` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `medical_release_form`;
CREATE TABLE `medical_release_form` (
  `medical_release_form_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `custom_task_id` int DEFAULT NULL,
  `case_id` int DEFAULT NULL,
  `case_type` varchar(100) DEFAULT NULL,
  `patient_first_name` varchar(100) DEFAULT NULL,
  `patient_last_name` varchar(100) DEFAULT NULL,
  `patient_nickname` varchar(100) DEFAULT NULL,
  `patient_phone_number` varchar(15) DEFAULT NULL,
  `patient_date_of_birth` date DEFAULT NULL,
  `patient_last_4_ssn` varchar(4) DEFAULT NULL,
  `patient_street_address` varchar(255) DEFAULT NULL,
  `patient_street_address_2` varchar(255) DEFAULT NULL,
  `patient_city` varchar(100) DEFAULT NULL,
  `patient_country` varchar(100) DEFAULT NULL,
  `patient_state` varchar(100) DEFAULT NULL,
  `patient_zip_code` varchar(10) DEFAULT NULL,
  `pregnancy_date` date DEFAULT NULL,
  `hospital_name` varchar(255) DEFAULT NULL,
  `hospital_street_address` varchar(255) DEFAULT NULL,
  `hospital_street_address_2` varchar(255) DEFAULT NULL,
  `hospital_city` varchar(100) DEFAULT NULL,
  `hospital_country` varchar(100) DEFAULT NULL,
  `hospital_state` varchar(100) DEFAULT NULL,
  `hospital_zip_code` varchar(10) DEFAULT NULL,
  `hospital_phone_number` varchar(50) DEFAULT NULL,
  `hospital_fax_number` varchar(50) DEFAULT NULL,
  `doctor_name` varchar(100) DEFAULT NULL,
  `clinic_name` varchar(255) DEFAULT NULL,
  `clinic_street_address` varchar(255) DEFAULT NULL,
  `clinic_street_address_2` varchar(255) DEFAULT NULL,
  `clinic_city` varchar(100) DEFAULT NULL,
  `clinic_country` varchar(100) DEFAULT NULL,
  `clinic_state` varchar(100) DEFAULT NULL,
  `clinic_zip_code` varchar(10) DEFAULT NULL,
  `clinic_phone_number` varchar(50) DEFAULT NULL,
  `clinic_fax_number` varchar(50) DEFAULT NULL,
  `patient_disclosure_authorization` tinyint(1) DEFAULT NULL,
  `patient_disclosure_items` varchar(255) DEFAULT NULL,
  `patient_full_legal_name` varchar(255) DEFAULT NULL,
  `patient_signature` text,
  `patient_signature_date` date DEFAULT NULL,
  `release_text` text,
  `authorization_text` text,
  `save_pdf` datetime DEFAULT NULL,
  `question_labels` mediumtext,
  `facility_index` int DEFAULT NULL,
  PRIMARY KEY (`medical_release_form_id`),
  UNIQUE KEY `ix_medical_release_form_task_facility_unique` (`custom_task_id`,`facility_index`),
  KEY `case_id` (`case_id`),
  CONSTRAINT `medical_release_form_ibfk_2` FOREIGN KEY (`case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `medical_release_form_ibfk_3` FOREIGN KEY (`custom_task_id`) REFERENCES `custom_task` (`task_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `migration_lock`;
CREATE TABLE `migration_lock` (
  `id` int NOT NULL,
  `is_locked` tinyint(1) NOT NULL DEFAULT '0',
  `locked_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `milestone`;
CREATE TABLE `milestone` (
  `milestone_id` int NOT NULL AUTO_INCREMENT,
  `milestone_base_id` int DEFAULT NULL,
  `order` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  PRIMARY KEY (`milestone_id`),
  KEY `milestone_base_id` (`milestone_base_id`),
  CONSTRAINT `milestone_ibfk_1` FOREIGN KEY (`milestone_base_id`) REFERENCES `milestone_base` (`milestone_base_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `milestone_base`;
CREATE TABLE `milestone_base` (
  `milestone_base_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  PRIMARY KEY (`milestone_base_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `notification`;
CREATE TABLE `notification` (
  `notification_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `related_admin_id` int DEFAULT NULL,
  `related_user_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `viewed` tinyint(1) DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `subject` varchar(100) DEFAULT NULL,
  `body_text` varchar(255) DEFAULT NULL,
  `extras` text,
  PRIMARY KEY (`notification_id`),
  KEY `admin_id` (`admin_id`),
  KEY `related_admin_id` (`related_admin_id`),
  KEY `notification_ibfk_1` (`gc_case_id`),
  KEY `notification_ibfk_3` (`ip_case_id`),
  KEY `notification_ibfk_5` (`contact_id`),
  KEY `notification_ibfk_6` (`related_user_id`),
  CONSTRAINT `notification_ibfk_1` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `notification_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `notification_ibfk_3` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `notification_ibfk_4` FOREIGN KEY (`related_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `notification_ibfk_5` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `notification_ibfk_6` FOREIGN KEY (`related_user_id`) REFERENCES `user` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `notification_preferences`;
CREATE TABLE `notification_preferences` (
  `notification_preferences_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `notification_type` varchar(100) DEFAULT NULL,
  `case_related` tinyint(1) DEFAULT NULL,
  `bell_notification` tinyint(1) DEFAULT '0',
  `email_notification` tinyint(1) DEFAULT '0',
  `role_list` text,
  `admin_list` text,
  `all_assigned_admins` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`notification_preferences_id`),
  UNIQUE KEY `notification_type` (`notification_type`),
  KEY `notification_preferences_ibfk_1` (`agency_id`),
  CONSTRAINT `notification_preferences_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `notification_preferences_chk_1` CHECK ((`all_assigned_admins` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `oauth_token`;
CREATE TABLE `oauth_token` (
  `token_id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `access_token_expiry` datetime DEFAULT NULL,
  `token_type` varchar(10) DEFAULT NULL,
  `access_token` text,
  `refresh_token` text,
  `sync_active` tinyint(1) DEFAULT NULL,
  `last_sync_at` datetime DEFAULT NULL,
  `last_sync_error` text,
  `last_synced_message_id` varchar(255) DEFAULT NULL,
  `consecutive_failures` int DEFAULT NULL,
  `disconnection_email_sent` datetime DEFAULT NULL,
  `historical_sync_requested` tinyint(1) DEFAULT NULL,
  `historical_sync_timeframe` varchar(20) DEFAULT NULL,
  `historical_sync_completed` tinyint(1) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `scopes` text,
  `account_id` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`token_id`),
  KEY `admin_id` (`admin_id`),
  KEY `token_type` (`token_type`),
  KEY `created_desc` (`created` DESC),
  CONSTRAINT `oauth_token_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `oauth_token_chk_1` CHECK ((`sync_active` in (0,1))),
  CONSTRAINT `oauth_token_chk_2` CHECK ((`historical_sync_requested` in (0,1))),
  CONSTRAINT `oauth_token_chk_3` CHECK ((`historical_sync_completed` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `pending_campaign_send`;
CREATE TABLE `pending_campaign_send` (
  `send_id` int NOT NULL AUTO_INCREMENT,
  `case_campaign_id` int NOT NULL,
  `case_campaign_flow_id` int NOT NULL,
  `error_id` int DEFAULT NULL,
  `scheduled_at` datetime NOT NULL,
  `sent_at` datetime DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `attempt_count` int NOT NULL DEFAULT '0',
  `status` enum('PENDING','SENT','FAILED','CANCELLED') NOT NULL DEFAULT 'PENDING',
  `claimed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`send_id`),
  KEY `case_campaign_flow_id` (`case_campaign_flow_id`),
  KEY `case_campaign_id` (`case_campaign_id`),
  KEY `error_id` (`error_id`),
  KEY `ix_pending_campaign_send_scheduled_at` (`scheduled_at`),
  KEY `ix_pending_campaign_send_status` (`status`),
  CONSTRAINT `pending_campaign_send_ibfk_1` FOREIGN KEY (`case_campaign_flow_id`) REFERENCES `case_campaign_flow` (`case_campaign_flow_id`) ON DELETE CASCADE,
  CONSTRAINT `pending_campaign_send_ibfk_2` FOREIGN KEY (`case_campaign_id`) REFERENCES `case_campaign` (`case_campaign_id`) ON DELETE CASCADE,
  CONSTRAINT `pending_campaign_send_ibfk_3` FOREIGN KEY (`error_id`) REFERENCES `err` (`error_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `pregnancy`;
CREATE TABLE `pregnancy` (
  `pregnancy_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `ed_case_id` int DEFAULT NULL,
  `transfer_id` int DEFAULT NULL,
  `pregnancy_loss_date` date DEFAULT NULL,
  `pregnancy_loss_type` varchar(25) DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `embryo_transfer_date` date DEFAULT NULL,
  `heartbeat_confirmation_date` date DEFAULT NULL,
  `ten_weeks` date DEFAULT NULL,
  `twelve_weeks` date DEFAULT NULL,
  `twenty_weeks` date DEFAULT NULL,
  `thirty_weeks` date DEFAULT NULL,
  `expected_delivery_date` date DEFAULT NULL,
  `expected_delivery_type` varchar(10) DEFAULT NULL,
  `csection_or_induction_date` date DEFAULT NULL,
  `notes` text,
  `heartbeat_count` varchar(5) DEFAULT NULL,
  `heartbeat_confirm_from_transfer` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`pregnancy_id`),
  KEY `case_id` (`case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `ed_case_id` (`ed_case_id`),
  CONSTRAINT `pregnancy_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `pregnancy_ibfk_2` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `pregnancy_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `pregnancy_ibfk_4` FOREIGN KEY (`ed_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `profile_appearance`;
CREATE TABLE `profile_appearance` (
  `profile_appearance_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `answer_font_weight` int DEFAULT NULL,
  `question_font_weight` int DEFAULT NULL,
  `answer_font_style` varchar(6) DEFAULT NULL,
  `question_font_style` varchar(6) DEFAULT NULL,
  `bg_card_body_color` varchar(7) DEFAULT NULL,
  `bg_card_header_color` varchar(7) DEFAULT NULL,
  `font_card_body_color` varchar(7) DEFAULT NULL,
  `font_card_header_color` varchar(7) DEFAULT NULL,
  `profile_font_family` varchar(17) DEFAULT NULL,
  `standardize_profile_image` datetime DEFAULT NULL,
  `print_logo_ip` datetime DEFAULT NULL,
  `print_logo_gc` datetime DEFAULT NULL,
  `print_logo_ed` datetime DEFAULT NULL,
  `print_logo_sd` datetime DEFAULT NULL,
  PRIMARY KEY (`profile_appearance_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `profile_appearance_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `profile_base`;
CREATE TABLE `profile_base` (
  `profile_id` int NOT NULL AUTO_INCREMENT,
  `profile_title` varchar(255) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `profile_type` varchar(20) DEFAULT NULL,
  `description` text,
  `fast_track` tinyint(1) DEFAULT '0',
  `active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`profile_id`),
  CONSTRAINT `profile_base_chk_1` CHECK ((`active` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `profile_change_history`;
CREATE TABLE `profile_change_history` (
  `profile_change_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `user_custom_profile_answer_id` int NOT NULL,
  `user_custom_profile_id` int NOT NULL,
  `admin_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `value` text,
  `answer_type` varchar(50) DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`profile_change_history_id`),
  KEY `admin_id` (`admin_id`),
  KEY `contact_id` (`contact_id`),
  KEY `ix_profile_change_history_answer_created` (`user_custom_profile_answer_id`,`created`),
  KEY `ix_profile_change_history_profile_created` (`user_custom_profile_id`,`created`),
  CONSTRAINT `profile_change_history_ibfk_1` FOREIGN KEY (`user_custom_profile_answer_id`) REFERENCES `user_custom_profile_answer` (`answer_id`) ON DELETE CASCADE,
  CONSTRAINT `profile_change_history_ibfk_2` FOREIGN KEY (`user_custom_profile_id`) REFERENCES `user_custom_profile` (`profile_id`) ON DELETE CASCADE,
  CONSTRAINT `profile_change_history_ibfk_3` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `profile_change_history_ibfk_4` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `profile_change_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `profile_change_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `profile_contact_history`;
CREATE TABLE `profile_contact_history` (
  `profile_contact_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `contact_id` int NOT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`profile_contact_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_profile_contact_history_contact_created` (`contact_id`,`created`),
  CONSTRAINT `profile_contact_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `profile_contact_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `profile_contact_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `profile_contact_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `profile_footer_settings`;
CREATE TABLE `profile_footer_settings` (
  `profile_footer_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `profile_type` varchar(10) NOT NULL,
  `footer_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `footer_text` text,
  `show_logo` tinyint(1) NOT NULL DEFAULT '0',
  `show_page_number` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`profile_footer_id`),
  UNIQUE KEY `uq_profile_footer_settings_agency_profile_type` (`agency_id`,`profile_type`),
  CONSTRAINT `profile_footer_settings_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `profile_footer_settings_chk_1` CHECK ((`footer_enabled` in (0,1))),
  CONSTRAINT `profile_footer_settings_chk_2` CHECK ((`show_logo` in (0,1))),
  CONSTRAINT `profile_footer_settings_chk_3` CHECK ((`show_page_number` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `profile_key`;
CREATE TABLE `profile_key` (
  `profile_key_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `profile_key` varchar(100) DEFAULT NULL,
  `profile_type` varchar(10) DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  PRIMARY KEY (`profile_key_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `profile_key_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `profile_question`;
CREATE TABLE `profile_question` (
  `question_id` int NOT NULL AUTO_INCREMENT,
  `dependent_on_question_id` int DEFAULT NULL,
  `profile_id` int DEFAULT NULL,
  `question_type` varchar(50) DEFAULT NULL,
  `question_text` text,
  `question_display` text,
  `question_order` int DEFAULT NULL,
  `question_code` varchar(255) DEFAULT NULL,
  `section` varchar(50) DEFAULT NULL,
  `section_order` int DEFAULT NULL,
  `section_columns` int DEFAULT '3',
  `answer_options` text,
  `required` tinyint(1) DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `admin_only` tinyint(1) DEFAULT '0',
  `viewable_on_profile` tinyint(1) DEFAULT '0',
  `dependent_answer` text,
  `updated` datetime DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  PRIMARY KEY (`question_id`),
  KEY `profile_id` (`profile_id`),
  KEY `dependent_on_question_id` (`dependent_on_question_id`),
  CONSTRAINT `profile_question_ibfk_1` FOREIGN KEY (`profile_id`) REFERENCES `profile_base` (`profile_id`) ON DELETE CASCADE,
  CONSTRAINT `profile_question_ibfk_2` FOREIGN KEY (`dependent_on_question_id`) REFERENCES `profile_question` (`question_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `program`;
CREATE TABLE `program` (
  `program_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `code` varchar(10) DEFAULT NULL,
  `description` text,
  PRIMARY KEY (`program_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `program_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `provider`;
CREATE TABLE `provider` (
  `provider_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `provider_type` varchar(20) DEFAULT NULL,
  `email_key` varchar(10) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `provider_name` varchar(255) DEFAULT NULL,
  `state` varchar(10) DEFAULT NULL,
  `zip_code` varchar(10) DEFAULT NULL,
  `country` varchar(50) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `fax_number` varchar(50) DEFAULT NULL,
  `city` varchar(255) DEFAULT NULL,
  `street_address_1` varchar(255) DEFAULT NULL,
  `street_address_2` varchar(255) DEFAULT NULL,
  `license_number` varchar(255) DEFAULT NULL,
  `facility_name` varchar(255) DEFAULT NULL,
  `website` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`provider_id`),
  UNIQUE KEY `email_key` (`email_key`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `provider_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `provider_contact_note`;
CREATE TABLE `provider_contact_note` (
  `note_id` int NOT NULL AUTO_INCREMENT,
  `created` date DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `provider_contact_id` int DEFAULT NULL,
  `note` text,
  PRIMARY KEY (`note_id`),
  KEY `provider_contact_note_ibfk_1` (`created_by_id`),
  CONSTRAINT `provider_contact_note_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `provider_document`;
CREATE TABLE `provider_document` (
  `provider_document_id` int NOT NULL AUTO_INCREMENT,
  `provider_id` int DEFAULT NULL,
  `title` varchar(100) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `document_type` varchar(100) DEFAULT NULL,
  `external_provider_id` int DEFAULT NULL,
  `size` int DEFAULT NULL,
  `uploaded_by` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  PRIMARY KEY (`provider_document_id`),
  KEY `provider_id` (`provider_id`),
  KEY `provider_document_admin_ibfk_1` (`uploaded_by`),
  CONSTRAINT `provider_document_ibfk_1` FOREIGN KEY (`provider_id`) REFERENCES `provider` (`provider_id`) ON DELETE CASCADE,
  CONSTRAINT `provider_document_ibfk_2` FOREIGN KEY (`uploaded_by`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `provider_note`;
CREATE TABLE `provider_note` (
  `note_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `updated_by_id` int DEFAULT NULL,
  `provider_id` int DEFAULT NULL,
  `note` text,
  `pinned` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`note_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `provider_note_ibfk_2` (`updated_by_id`),
  CONSTRAINT `provider_note_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `provider_note_ibfk_2` FOREIGN KEY (`updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `provider_user`;
CREATE TABLE `provider_user` (
  `provider_user_id` int NOT NULL AUTO_INCREMENT,
  `provider_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `extension_number` int DEFAULT NULL,
  `provider_user_type` varchar(20) DEFAULT NULL,
  `role` varchar(50) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `license_number` varchar(255) DEFAULT NULL,
  `email_key` varchar(10) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `note` text,
  PRIMARY KEY (`provider_user_id`),
  UNIQUE KEY `email_key` (`email_key`),
  KEY `provider_id` (`provider_id`),
  CONSTRAINT `provider_user_ibfk_1` FOREIGN KEY (`provider_id`) REFERENCES `provider` (`provider_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `recaptcha_submission`;
CREATE TABLE `recaptcha_submission` (
  `recaptcha_submission_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `form_type` varchar(50) NOT NULL,
  `action` varchar(100) DEFAULT NULL,
  `score` float DEFAULT NULL,
  `threshold` float DEFAULT NULL,
  `passed` tinyint(1) DEFAULT NULL,
  `label` varchar(50) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `hostname` varchar(255) DEFAULT NULL,
  `error_codes` text,
  `raw_response` text,
  `form_data` text,
  PRIMARY KEY (`recaptcha_submission_id`),
  CONSTRAINT `recaptcha_submission_chk_1` CHECK ((`passed` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `report_widgets`;
CREATE TABLE `report_widgets` (
  `report_widget_id` int NOT NULL AUTO_INCREMENT,
  `report_name` varchar(25) DEFAULT NULL,
  `report_type` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`report_widget_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `retrieval`;
CREATE TABLE `retrieval` (
  `retrieval_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `ed_case_id` int DEFAULT NULL,
  `ed_contact_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `completed` tinyint(1) DEFAULT NULL,
  `retrieval_date` datetime DEFAULT NULL,
  `retrieval_number` int DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `clinic_contact_id` int DEFAULT NULL,
  `egg_source_type` varchar(50) DEFAULT NULL,
  `egg_source_id` varchar(100) DEFAULT NULL,
  `sperm_source_type` varchar(15) DEFAULT NULL,
  `sperm_source_id` int DEFAULT NULL,
  `sperm_source_details` varchar(100) DEFAULT NULL,
  `clinic_name_user_provided` varchar(255) DEFAULT NULL,
  `clinic_name` varchar(255) DEFAULT NULL,
  `clinic_address` text,
  `physician_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `cycle_number` varchar(100) DEFAULT NULL,
  `eggs_retrieved` varchar(100) DEFAULT NULL,
  `eggs_fertilized` varchar(100) DEFAULT NULL,
  `embryos` varchar(100) DEFAULT NULL,
  `embryo_quality` varchar(100) DEFAULT NULL,
  `embryos_transferred` varchar(100) DEFAULT NULL,
  `pregnancy_result` varchar(100) DEFAULT NULL,
  `eggs_remaining` varchar(100) DEFAULT NULL,
  `pgta_tested` varchar(100) DEFAULT NULL,
  `pgtm_tested` tinyint(1) DEFAULT NULL,
  `notes` text,
  `egg_fresh_type` varchar(20) DEFAULT NULL,
  `age_at_frozen` varchar(36) DEFAULT NULL,
  PRIMARY KEY (`retrieval_id`),
  KEY `case_id` (`case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `clinic_contact_id` (`clinic_contact_id`),
  KEY `sperm_source_id` (`sperm_source_id`),
  KEY `ed_case_id` (`ed_case_id`),
  CONSTRAINT `retrieval_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `retrieval_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `retrieval_ibfk_3` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `retrieval_ibfk_4` FOREIGN KEY (`clinic_contact_id`) REFERENCES `clinic_contact` (`clinic_contact_id`) ON DELETE CASCADE,
  CONSTRAINT `retrieval_ibfk_5` FOREIGN KEY (`sperm_source_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `retrieval_ibfk_6` FOREIGN KEY (`ed_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `retrieval_batch`;
CREATE TABLE `retrieval_batch` (
  `batch_id` int NOT NULL AUTO_INCREMENT,
  `retrieval_id` int NOT NULL,
  `batch_number` int NOT NULL,
  `eggs_per_batch` int DEFAULT NULL,
  `notes` text,
  `created` datetime DEFAULT NULL,
  PRIMARY KEY (`batch_id`),
  UNIQUE KEY `unique_retrieval_batch` (`retrieval_id`,`batch_number`),
  CONSTRAINT `retrieval_batch_ibfk_1` FOREIGN KEY (`retrieval_id`) REFERENCES `retrieval` (`retrieval_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `retrieval_batch_history`;
CREATE TABLE `retrieval_batch_history` (
  `retrieval_batch_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `batch_id` int NOT NULL,
  `retrieval_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`retrieval_batch_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_retrieval_batch_history_batch_created` (`batch_id`,`created`),
  CONSTRAINT `retrieval_batch_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `retrieval_batch_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `retrieval_batch_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `retrieval_batch_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `retrieval_history`;
CREATE TABLE `retrieval_history` (
  `retrieval_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `retrieval_id` int NOT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`retrieval_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_retrieval_history_retrieval_created` (`retrieval_id`,`created`),
  CONSTRAINT `retrieval_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `retrieval_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `retrieval_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `retrieval_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `saved_view`;
CREATE TABLE `saved_view` (
  `saved_view_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `admin_id` int NOT NULL,
  `view_key` varchar(64) NOT NULL,
  `scope_key` varchar(64) NOT NULL DEFAULT '',
  `name` varchar(80) NOT NULL,
  `params` text NOT NULL,
  `is_default` tinyint(1) NOT NULL DEFAULT '0',
  `sort_order` int NOT NULL DEFAULT '0',
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  PRIMARY KEY (`saved_view_id`),
  KEY `agency_id` (`agency_id`),
  KEY `ix_saved_view_lookup` (`admin_id`,`view_key`,`scope_key`),
  CONSTRAINT `saved_view_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `saved_view_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE CASCADE,
  CONSTRAINT `saved_view_chk_1` CHECK ((`is_default` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_profile_document`;
CREATE TABLE `sd_profile_document` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `sd_profile_document_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_profile_image`;
CREATE TABLE `sd_profile_image` (
  `image_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `image_type` varchar(15) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `edited_path` varchar(255) DEFAULT NULL,
  `is_visible` tinyint(1) DEFAULT NULL,
  `caption` varchar(100) DEFAULT NULL,
  `order` int DEFAULT NULL,
  PRIMARY KEY (`image_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `sd_profile_image_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `sd_profile_image_chk_1` CHECK ((`is_visible` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_profile_video`;
CREATE TABLE `sd_profile_video` (
  `video_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `uploaded` datetime DEFAULT NULL,
  `video_path` varchar(255) DEFAULT NULL,
  `length` int DEFAULT NULL,
  PRIMARY KEY (`video_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `sd_profile_video_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval`;
CREATE TABLE `sd_retrieval` (
  `sd_retrieval_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int DEFAULT NULL,
  `sd_case_id` int DEFAULT NULL,
  `sd_contact_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `clinic_name_user_provided` varchar(255) DEFAULT NULL,
  `clinic_name` varchar(255) DEFAULT NULL,
  `completed` tinyint(1) DEFAULT NULL,
  `retrieval_number` varchar(100) DEFAULT NULL,
  `date_first_retrieval` datetime DEFAULT NULL,
  `num_of_vials` varchar(100) DEFAULT NULL,
  `over_number_of_days` varchar(100) DEFAULT NULL,
  `volume_per_vial` varchar(100) DEFAULT NULL,
  `sperm_quality` varchar(100) DEFAULT NULL,
  `sperm_motility` varchar(100) DEFAULT NULL,
  `retrieval_deposit_type` varchar(100) DEFAULT NULL,
  `physician_name` varchar(255) DEFAULT NULL,
  `age_at_freeze` varchar(100) DEFAULT NULL,
  `sperm_source_type` varchar(15) DEFAULT NULL,
  `sperm_source_id` int DEFAULT NULL,
  `sperm_source_details` varchar(100) DEFAULT NULL,
  `num_useable_embryos` varchar(100) DEFAULT NULL,
  `pgt_testing` tinyint(1) DEFAULT NULL,
  `embryo_quality` varchar(100) DEFAULT NULL,
  `pregnancy_confirmed` varchar(10) DEFAULT NULL,
  `notes` text,
  `num_of_visits` int DEFAULT NULL,
  PRIMARY KEY (`sd_retrieval_id`),
  KEY `case_id` (`case_id`),
  KEY `clinic_id` (`clinic_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `sperm_source_id` (`sperm_source_id`),
  CONSTRAINT `sd_retrieval_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `sd_retrieval_ibfk_2` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE,
  CONSTRAINT `sd_retrieval_ibfk_3` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_ibfk_5` FOREIGN KEY (`sperm_source_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `sd_retrieval_chk_1` CHECK ((`completed` in (0,1))),
  CONSTRAINT `sd_retrieval_chk_2` CHECK ((`pgt_testing` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval_batch`;
CREATE TABLE `sd_retrieval_batch` (
  `batch_id` int NOT NULL AUTO_INCREMENT,
  `sd_retrieval_id` int NOT NULL,
  `batch_number` int NOT NULL,
  `vials_per_batch` int DEFAULT NULL,
  `volume_per_batch` varchar(100) DEFAULT NULL,
  `notes` text,
  `created` datetime DEFAULT NULL,
  PRIMARY KEY (`batch_id`),
  UNIQUE KEY `unique_sd_retrieval_batch` (`sd_retrieval_id`,`batch_number`),
  CONSTRAINT `sd_retrieval_batch_ibfk_1` FOREIGN KEY (`sd_retrieval_id`) REFERENCES `sd_retrieval` (`sd_retrieval_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval_batch_history`;
CREATE TABLE `sd_retrieval_batch_history` (
  `sd_retrieval_batch_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `batch_id` int NOT NULL,
  `sd_retrieval_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`sd_retrieval_batch_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_sd_retrieval_batch_history_batch_created` (`batch_id`,`created`),
  CONSTRAINT `sd_retrieval_batch_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_batch_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_batch_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `sd_retrieval_batch_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval_date`;
CREATE TABLE `sd_retrieval_date` (
  `sd_retrieval_date_id` int NOT NULL AUTO_INCREMENT,
  `sd_retrieval_id` int NOT NULL,
  `visit_number` int NOT NULL,
  `retrieval_date` datetime DEFAULT NULL,
  `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`sd_retrieval_date_id`),
  UNIQUE KEY `unique_retrieval_visit` (`sd_retrieval_id`,`visit_number`),
  CONSTRAINT `sd_retrieval_date_ibfk_1` FOREIGN KEY (`sd_retrieval_id`) REFERENCES `sd_retrieval` (`sd_retrieval_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval_date_history`;
CREATE TABLE `sd_retrieval_date_history` (
  `sd_retrieval_date_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `sd_retrieval_date_id` int NOT NULL,
  `sd_retrieval_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`sd_retrieval_date_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_sd_retrieval_date_history_date_created` (`sd_retrieval_date_id`,`created`),
  CONSTRAINT `sd_retrieval_date_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_date_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_date_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `sd_retrieval_date_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sd_retrieval_history`;
CREATE TABLE `sd_retrieval_history` (
  `sd_retrieval_history_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `sd_retrieval_id` int NOT NULL,
  `contact_id` int DEFAULT NULL,
  `field_name` varchar(100) NOT NULL,
  `value` text,
  `change_type` varchar(20) NOT NULL,
  `actor_admin_id` int DEFAULT NULL,
  `actor_contact_id` int DEFAULT NULL,
  `is_ai_agent` tinyint(1) NOT NULL DEFAULT '0',
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`sd_retrieval_history_id`),
  KEY `actor_admin_id` (`actor_admin_id`),
  KEY `actor_contact_id` (`actor_contact_id`),
  KEY `ix_sd_retrieval_history_retrieval_created` (`sd_retrieval_id`,`created`),
  CONSTRAINT `sd_retrieval_history_ibfk_1` FOREIGN KEY (`actor_admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_history_ibfk_2` FOREIGN KEY (`actor_contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `sd_retrieval_history_chk_1` CHECK ((`is_ai_agent` in (0,1))),
  CONSTRAINT `sd_retrieval_history_chk_2` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sendgrid_event`;
CREATE TABLE `sendgrid_event` (
  `sendgrid_event_id` int NOT NULL AUTO_INCREMENT,
  `sg_event_id` varchar(64) DEFAULT NULL,
  `sg_message_id` varchar(255) DEFAULT NULL,
  `event` varchar(32) DEFAULT NULL,
  `type` varchar(32) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `reason` text,
  `status` varchar(32) DEFAULT NULL,
  `bounce_classification` varchar(64) DEFAULT NULL,
  `email_ref` varchar(128) DEFAULT NULL,
  `event_timestamp` datetime DEFAULT NULL,
  `raw` text,
  `created` datetime DEFAULT NULL,
  PRIMARY KEY (`sendgrid_event_id`),
  UNIQUE KEY `ux_sendgrid_event_sg_event_id` (`sg_event_id`),
  KEY `ix_sendgrid_event_event_timestamp` (`event_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `service_level`;
CREATE TABLE `service_level` (
  `service_level_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `code` varchar(10) DEFAULT NULL,
  `description` text,
  PRIMARY KEY (`service_level_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `service_level_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `settings_change_log`;
CREATE TABLE `settings_change_log` (
  `settings_change_log_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `section` varchar(50) DEFAULT NULL,
  `field_name` varchar(100) DEFAULT NULL,
  `old_value` text,
  `new_value` text,
  `is_system_generated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`settings_change_log_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `settings_change_log_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `settings_change_log_chk_1` CHECK ((`is_system_generated` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `signed_contract`;
CREATE TABLE `signed_contract` (
  `signed_contract_id` int NOT NULL AUTO_INCREMENT,
  `case_contract_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `np_user_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `custom_task_id` int DEFAULT NULL,
  `sign_date` datetime DEFAULT NULL,
  `electronic_agreement` tinyint(1) DEFAULT NULL,
  `ip_address` varchar(50) DEFAULT NULL,
  `contract_signature` varchar(255) DEFAULT NULL,
  `initials` text,
  PRIMARY KEY (`signed_contract_id`),
  KEY `case_contract_id` (`case_contract_id`),
  KEY `contact_id` (`contact_id`),
  KEY `admin_id` (`admin_id`),
  KEY `signed_contract_ibfk_90` (`np_user_id`),
  KEY `custom_task_id` (`custom_task_id`),
  CONSTRAINT `signed_contract_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `signed_contract_ibfk_2` FOREIGN KEY (`case_contract_id`) REFERENCES `case_contract` (`case_contract_id`) ON DELETE CASCADE,
  CONSTRAINT `signed_contract_ibfk_4` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `signed_contract_ibfk_90` FOREIGN KEY (`np_user_id`) REFERENCES `user_np` (`np_user_id`),
  CONSTRAINT `signed_contract_ibfk_91` FOREIGN KEY (`custom_task_id`) REFERENCES `custom_task` (`task_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `sms_template`;
CREATE TABLE `sms_template` (
  `sms_template_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `backend_title` varchar(100) DEFAULT NULL,
  `last_updated_id` int DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `backend_description` varchar(255) DEFAULT NULL,
  `html_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `sms_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_template` tinyint(1) DEFAULT NULL,
  `category` enum('CAMPAIGN','WORKFLOW','MASS_TEXT','NOTIFICATION','GENERAL') NOT NULL DEFAULT 'GENERAL',
  PRIMARY KEY (`sms_template_id`),
  KEY `last_updated_id` (`last_updated_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `sms_template_ibfk_1` FOREIGN KEY (`last_updated_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `sms_template_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `status`;
CREATE TABLE `status` (
  `status_id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int DEFAULT NULL,
  `status` varchar(100) DEFAULT NULL,
  `active` tinyint(1) DEFAULT '1',
  `stage` varchar(20) DEFAULT NULL,
  `contact_type` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`status_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `status_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `subscription_info`;
CREATE TABLE `subscription_info` (
  `subscription_info_id` int NOT NULL AUTO_INCREMENT,
  `current_plans` varchar(255) DEFAULT NULL,
  `recommended_plans` varchar(255) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `payment_start_date` datetime DEFAULT NULL,
  `count_start_date` datetime DEFAULT NULL,
  `gc_ip_matches` int DEFAULT NULL,
  `gc_ip_screening` int DEFAULT NULL,
  `gc_ip_intake` int DEFAULT NULL,
  `ed_ip_matches` int DEFAULT NULL,
  `ed_ip_screening` int DEFAULT NULL,
  `ed_ip_intake` int DEFAULT NULL,
  PRIMARY KEY (`subscription_info_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `template`;
CREATE TABLE `template` (
  `template_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `template_title` varchar(100) DEFAULT NULL,
  `case_type_example` text,
  `template_type` varchar(255) DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `fast_track` tinyint(1) DEFAULT '0',
  `snippet` tinyint(1) DEFAULT '0',
  `allow_substages` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`template_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `template_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `template_stage`;
CREATE TABLE `template_stage` (
  `stage_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `ordering` int DEFAULT NULL,
  `required_complete` int DEFAULT NULL,
  `date_depricated` datetime DEFAULT NULL,
  PRIMARY KEY (`stage_id`),
  KEY `template_id` (`template_id`),
  CONSTRAINT `template_stage_ibfk_1` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `template_sub_stage`;
CREATE TABLE `template_sub_stage` (
  `sub_stage_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `template_stage_id` int DEFAULT NULL,
  `admin_only` tinyint(1) DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `ordering` int DEFAULT NULL,
  PRIMARY KEY (`sub_stage_id`),
  KEY `template_id` (`template_id`),
  KEY `template_stage_id` (`template_stage_id`),
  CONSTRAINT `template_sub_stage_ibfk_1` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE CASCADE,
  CONSTRAINT `template_sub_stage_ibfk_2` FOREIGN KEY (`template_stage_id`) REFERENCES `template_stage` (`stage_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `template_task`;
CREATE TABLE `template_task` (
  `task_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `template_sub_stage_id` int DEFAULT NULL,
  `admin_only` tinyint(1) DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `ordering` int DEFAULT NULL,
  `email_template_id` int DEFAULT NULL,
  `form_id` int DEFAULT NULL,
  `assigned_admin_type` varchar(255) DEFAULT NULL,
  `notify_admin_type` varchar(255) DEFAULT NULL,
  `needs_approval` tinyint(1) DEFAULT NULL,
  `has_contract` tinyint(1) DEFAULT NULL,
  `contract_id` int DEFAULT NULL,
  `require_document` int DEFAULT NULL,
  `required_complete` int DEFAULT NULL,
  `required` tinyint(1) DEFAULT NULL,
  `profile_task` tinyint(1) DEFAULT '0',
  `view_donors` tinyint(1) DEFAULT NULL,
  `notify_admin_email` tinyint DEFAULT '0',
  `date_depricated` datetime DEFAULT NULL,
  `old_task_id` int DEFAULT NULL,
  `description_updated` datetime DEFAULT NULL,
  `description_updated_by_id` int DEFAULT NULL,
  `sms_template_id` int DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `email_template_id` (`email_template_id`),
  KEY `form_id` (`form_id`),
  KEY `contract_id` (`contract_id`),
  KEY `required_complete` (`required_complete`),
  KEY `template_id` (`template_id`),
  KEY `template_sub_stage_id` (`template_sub_stage_id`),
  KEY `description_updated_by_id` (`description_updated_by_id`),
  KEY `old_task_id` (`old_task_id`),
  KEY `template_task_ibfk_sms_template` (`sms_template_id`),
  CONSTRAINT `template_task_ibfk_1` FOREIGN KEY (`template_id`) REFERENCES `template` (`template_id`) ON DELETE CASCADE,
  CONSTRAINT `template_task_ibfk_2` FOREIGN KEY (`template_sub_stage_id`) REFERENCES `template_sub_stage` (`sub_stage_id`) ON DELETE CASCADE,
  CONSTRAINT `template_task_ibfk_3` FOREIGN KEY (`form_id`) REFERENCES `form` (`form_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_4` FOREIGN KEY (`email_template_id`) REFERENCES `email_template` (`email_template_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_5` FOREIGN KEY (`required_complete`) REFERENCES `template_task` (`task_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_6` FOREIGN KEY (`contract_id`) REFERENCES `contract` (`contract_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_7` FOREIGN KEY (`description_updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `template_task_ibfk_8` FOREIGN KEY (`old_task_id`) REFERENCES `template_task` (`task_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_9` FOREIGN KEY (`description_updated_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `template_task_ibfk_sms_template` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `template_task_document`;
CREATE TABLE `template_task_document` (
  `reference_id` int NOT NULL AUTO_INCREMENT,
  `task_id` int DEFAULT NULL,
  `document_id` int DEFAULT NULL,
  PRIMARY KEY (`reference_id`),
  KEY `task_id` (`task_id`),
  KEY `document_id` (`document_id`),
  CONSTRAINT `template_task_document_ibfk_1` FOREIGN KEY (`task_id`) REFERENCES `template_task` (`task_id`) ON DELETE CASCADE,
  CONSTRAINT `template_task_document_ibfk_2` FOREIGN KEY (`document_id`) REFERENCES `agency_document` (`document_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `text_consent_log`;
CREATE TABLE `text_consent_log` (
  `text_consent_log_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `old_status` varchar(30) DEFAULT NULL,
  `new_status` varchar(30) NOT NULL,
  `source` varchar(50) NOT NULL,
  `admin_id` int DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `disclosure_text` text,
  PRIMARY KEY (`text_consent_log_id`),
  KEY `admin_id` (`admin_id`),
  KEY `contact_id` (`contact_id`),
  CONSTRAINT `text_consent_log_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `text_consent_log_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `text_message`;
CREATE TABLE `text_message` (
  `text_message_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `twilio_sid` varchar(50) DEFAULT NULL,
  `twilio_status` enum('QUEUED','SENT','DELIVERED','UNDELIVERED','FAILED') NOT NULL,
  `twilio_error_code` int DEFAULT NULL,
  `twilio_error_message` varchar(500) DEFAULT NULL,
  `direction` varchar(10) DEFAULT NULL,
  `from_number` varchar(20) DEFAULT NULL,
  `to_number` varchar(20) NOT NULL,
  `body` text,
  `media_url` varchar(500) DEFAULT NULL,
  `segment_count` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `source` varchar(30) NOT NULL,
  `source_id` int DEFAULT NULL,
  `sms_template_id` int DEFAULT NULL,
  `scheduled_send_at` datetime DEFAULT NULL,
  `conversation_id` varchar(50) DEFAULT NULL,
  `reply_to_id` int DEFAULT NULL,
  PRIMARY KEY (`text_message_id`),
  UNIQUE KEY `twilio_sid` (`twilio_sid`),
  KEY `admin_id` (`admin_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `sms_template_id` (`sms_template_id`),
  KEY `idx_text_message_contact` (`contact_id`),
  KEY `idx_text_message_created` (`created`),
  KEY `idx_text_message_source` (`source`,`source_id`),
  KEY `idx_text_message_status` (`twilio_status`),
  CONSTRAINT `text_message_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `text_message_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE SET NULL,
  CONSTRAINT `text_message_ibfk_3` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `text_message_ibfk_4` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `text_message_ibfk_5` FOREIGN KEY (`sms_template_id`) REFERENCES `sms_template` (`sms_template_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `text_message_status_event`;
CREATE TABLE `text_message_status_event` (
  `text_message_status_event_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `twilio_sid` varchar(50) NOT NULL,
  `twilio_status` enum('QUEUED','SENT','DELIVERED','UNDELIVERED','FAILED') NOT NULL,
  `twilio_error_code` int DEFAULT NULL,
  `twilio_error_message` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`text_message_status_event_id`),
  UNIQUE KEY `twilio_sid` (`twilio_sid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `third_party_user`;
CREATE TABLE `third_party_user` (
  `third_party_id` int NOT NULL AUTO_INCREMENT,
  `active` tinyint(1) DEFAULT '1',
  `created` datetime DEFAULT NULL,
  `first_name` varchar(255) DEFAULT NULL,
  `last_name` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `telephone_number` varchar(20) DEFAULT NULL,
  `fax_number` varchar(20) DEFAULT NULL,
  `address_1` varchar(255) DEFAULT NULL,
  `address_2` varchar(255) DEFAULT NULL,
  `city` varchar(255) DEFAULT NULL,
  `state` varchar(5) DEFAULT NULL,
  `zip_code` varchar(10) DEFAULT NULL,
  `country` varchar(100) DEFAULT NULL,
  `current_coordinator` varchar(255) DEFAULT NULL,
  `role` varchar(255) DEFAULT NULL,
  `referral` varchar(255) DEFAULT NULL,
  `comments` text,
  `email_key` varchar(255) DEFAULT NULL,
  `pass_hash` text,
  `first_login` datetime DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `ip_address` varchar(255) DEFAULT NULL,
  `electronic_signature` varchar(255) DEFAULT NULL,
  `electronic_agreement` datetime DEFAULT NULL,
  `recaptcha_submission_id` int DEFAULT NULL,
  PRIMARY KEY (`third_party_id`),
  KEY `agency_id` (`agency_id`),
  KEY `recaptcha_submission_id` (`recaptcha_submission_id`),
  CONSTRAINT `third_party_user_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`),
  CONSTRAINT `third_party_user_ibfk_2` FOREIGN KEY (`recaptcha_submission_id`) REFERENCES `recaptcha_submission` (`recaptcha_submission_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `transfer`;
CREATE TABLE `transfer` (
  `transfer_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `cycle_number` int DEFAULT NULL,
  `case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `created_by_id` int DEFAULT NULL,
  `clinic_id` int DEFAULT NULL,
  `clinic_name` varchar(255) DEFAULT NULL,
  `clinic_contact_id` int DEFAULT NULL,
  `retrieval_id` int DEFAULT NULL,
  `transfer_date` datetime DEFAULT NULL,
  `transfer_type` varchar(10) DEFAULT NULL,
  `sperm_source_type` varchar(15) DEFAULT NULL,
  `sperm_source_id` int DEFAULT NULL,
  `sperm_source_details` varchar(100) DEFAULT NULL,
  `egg_source_type` varchar(50) DEFAULT NULL,
  `medication_start_date` date DEFAULT NULL,
  `gc_estrace_start_date` date DEFAULT NULL,
  `lining_check_date` date DEFAULT NULL,
  `clinic_address` text,
  `physician_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `transfer_number` varchar(100) DEFAULT NULL,
  `embryos` varchar(100) DEFAULT NULL,
  `embryos_remaining` varchar(100) DEFAULT NULL,
  `transfer_result` varchar(15) DEFAULT NULL,
  `transfer_result_date` date DEFAULT NULL,
  `ultrasound_heartbeat_date` date DEFAULT NULL,
  `ultrasound_result` varchar(100) DEFAULT NULL,
  `pregnancy_confirmed` varchar(10) DEFAULT NULL,
  `pregnancy_loss_date` date DEFAULT NULL,
  `pregnancy_loss_type` varchar(25) DEFAULT NULL,
  `notes` text,
  `sex_of_embryo` varchar(100) DEFAULT NULL,
  `pregnancy_id` int DEFAULT NULL,
  `age_of_embryo` int DEFAULT NULL,
  `pregnancy_calculator_linked` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`transfer_id`),
  KEY `case_id` (`case_id`),
  KEY `created_by_id` (`created_by_id`),
  KEY `retrieval_id` (`retrieval_id`),
  KEY `clinic_contact_id` (`clinic_contact_id`),
  KEY `sperm_source_id` (`sperm_source_id`),
  KEY `gc_case_id` (`gc_case_id`),
  KEY `clinic_id` (`clinic_id`),
  CONSTRAINT `transfer_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `transfer_ibfk_2` FOREIGN KEY (`created_by_id`) REFERENCES `admin` (`admin_id`) ON DELETE SET NULL,
  CONSTRAINT `transfer_ibfk_3` FOREIGN KEY (`retrieval_id`) REFERENCES `retrieval` (`retrieval_id`),
  CONSTRAINT `transfer_ibfk_4` FOREIGN KEY (`clinic_contact_id`) REFERENCES `clinic_contact` (`clinic_contact_id`) ON DELETE CASCADE,
  CONSTRAINT `transfer_ibfk_5` FOREIGN KEY (`sperm_source_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `transfer_ibfk_6` FOREIGN KEY (`gc_case_id`) REFERENCES `gc_case` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `transfer_ibfk_7` FOREIGN KEY (`clinic_id`) REFERENCES `clinic` (`clinic_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `contact_id` int DEFAULT NULL,
  `user_type` varchar(50) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `available` tinyint(1) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `email_key` varchar(100) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `shared_auth_key` varchar(20) DEFAULT NULL,
  `gurgle_auth_key` varchar(32) DEFAULT NULL,
  `active_access_key` varchar(100) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `has_match` tinyint(1) DEFAULT NULL,
  `translation_language` varchar(20) DEFAULT NULL,
  `time_zone_pytz` varchar(100) DEFAULT 'UTC',
  `confirmed_email` tinyint(1) DEFAULT '0',
  `gurgle_alert_sent` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `email_key` (`email_key`),
  UNIQUE KEY `gurgle_auth_key` (`gurgle_auth_key`),
  KEY `contact_id` (`contact_id`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `user_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `user_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `user_custom_profile`;
CREATE TABLE `user_custom_profile` (
  `profile_id` int NOT NULL AUTO_INCREMENT,
  `base_profile_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `family_id` int DEFAULT NULL,
  `user_submitted` tinyint(1) DEFAULT NULL,
  `custom_visibility` text,
  `custom_labels` text,
  `edit_history` text,
  `profile_image_path` varchar(255) DEFAULT NULL,
  `edited_profile_image_path` varchar(255) DEFAULT NULL,
  `first_submit` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`profile_id`),
  KEY `base_profile_id` (`base_profile_id`),
  KEY `contact_id` (`contact_id`),
  KEY `family_id` (`family_id`),
  CONSTRAINT `user_custom_profile_ibfk_1` FOREIGN KEY (`base_profile_id`) REFERENCES `profile_base` (`profile_id`) ON DELETE CASCADE,
  CONSTRAINT `user_custom_profile_ibfk_2` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `user_custom_profile_ibfk_3` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `user_custom_profile_answer`;
CREATE TABLE `user_custom_profile_answer` (
  `answer_id` int NOT NULL AUTO_INCREMENT,
  `base_question_id` int DEFAULT NULL,
  `custom_section_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `date_answer` date DEFAULT NULL,
  `number_answer` int DEFAULT NULL,
  `boolean_answer` tinyint(1) DEFAULT NULL,
  `text_answer` text,
  `multiple_answer` text,
  `profile_image_id` int DEFAULT NULL,
  PRIMARY KEY (`answer_id`),
  KEY `base_question_id` (`base_question_id`),
  KEY `custom_section_id` (`custom_section_id`),
  CONSTRAINT `user_custom_profile_answer_ibfk_2` FOREIGN KEY (`base_question_id`) REFERENCES `profile_question` (`question_id`) ON DELETE CASCADE,
  CONSTRAINT `user_custom_profile_answer_ibfk_3` FOREIGN KEY (`custom_section_id`) REFERENCES `user_custom_profile_section` (`section_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `user_custom_profile_section`;
CREATE TABLE `user_custom_profile_section` (
  `section_id` int NOT NULL AUTO_INCREMENT,
  `custom_profile_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  `title` varchar(50) DEFAULT NULL,
  `section_type` varchar(10) DEFAULT NULL,
  `ordering` int DEFAULT NULL,
  `columns` int DEFAULT NULL,
  `orientation` tinyint(1) DEFAULT NULL,
  `page_break_after` tinyint(1) DEFAULT NULL,
  `is_default` tinyint(1) DEFAULT NULL,
  `is_visible` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`section_id`),
  KEY `custom_profile_id` (`custom_profile_id`),
  CONSTRAINT `user_custom_profile_section_ibfk_1` FOREIGN KEY (`custom_profile_id`) REFERENCES `user_custom_profile` (`profile_id`) ON DELETE CASCADE,
  CONSTRAINT `user_custom_profile_section_chk_1` CHECK ((`is_visible` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `user_form`;
CREATE TABLE `user_form` (
  `user_form_id` int NOT NULL AUTO_INCREMENT,
  `parent_form_id` int DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `contact_id` int DEFAULT NULL,
  `ip_case_id` int DEFAULT NULL,
  `gc_case_id` int DEFAULT NULL,
  `marketing_json` text,
  `save_pdf` datetime DEFAULT NULL,
  PRIMARY KEY (`user_form_id`),
  KEY `parent_form_id` (`parent_form_id`),
  KEY `agency_id` (`agency_id`),
  KEY `contact_id` (`contact_id`),
  KEY `ip_case_id` (`ip_case_id`),
  KEY `gc_case_id` (`gc_case_id`),
  CONSTRAINT `user_form_ibfk_1` FOREIGN KEY (`parent_form_id`) REFERENCES `form` (`form_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_ibfk_2` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_ibfk_3` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`contact_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_ibfk_4` FOREIGN KEY (`ip_case_id`) REFERENCES `ip_case` (`case_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `user_form_answer`;
CREATE TABLE `user_form_answer` (
  `user_form_question_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `user_form_id` int DEFAULT NULL,
  `form_question_id` int DEFAULT NULL,
  `question_json` mediumtext,
  `date_answer` date DEFAULT NULL,
  `number_answer` int DEFAULT NULL,
  `boolean_answer` tinyint(1) DEFAULT NULL,
  `text_answer` text,
  `multiple_answer` text,
  `document_id` int DEFAULT NULL,
  `contact_document_id` int DEFAULT NULL,
  `updated` datetime DEFAULT NULL,
  PRIMARY KEY (`user_form_question_id`),
  KEY `user_form_id` (`user_form_id`),
  KEY `form_question_id` (`form_question_id`),
  KEY `user_form_answer_ibfk_89` (`contact_document_id`),
  KEY `user_form_answer_ibfk_1` (`document_id`),
  CONSTRAINT `user_form_answer_ibfk_1` FOREIGN KEY (`document_id`) REFERENCES `case_document` (`case_document_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_answer_ibfk_2` FOREIGN KEY (`contact_document_id`) REFERENCES `contact_document` (`document_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_answer_ibfk_3` FOREIGN KEY (`form_question_id`) REFERENCES `form_question` (`form_question_id`) ON DELETE CASCADE,
  CONSTRAINT `user_form_answer_ibfk_4` FOREIGN KEY (`user_form_id`) REFERENCES `user_form` (`user_form_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `user_np`;
CREATE TABLE `user_np` (
  `np_user_id` int NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `email_key` varchar(20) DEFAULT NULL,
  `user_type` varchar(50) DEFAULT NULL,
  `pass_hash` varchar(255) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `profile_path` varchar(255) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `phone` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`np_user_id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `email_key` (`email_key`),
  KEY `agency_id` (`agency_id`),
  CONSTRAINT `user_np_ibfk_1` FOREIGN KEY (`agency_id`) REFERENCES `agency` (`agency_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

SET FOREIGN_KEY_CHECKS=1;
