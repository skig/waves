#include <zephyr/types.h>
#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/bluetooth/cs.h>
#include <zephyr/settings/settings.h>
#include <dk_buttons_and_leds.h>

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app_main, LOG_LEVEL_INF);

#define CON_STATUS_LED DK_LED1
#define CS_CONFIG_ID   0

static K_SEM_DEFINE(sem_connected, 0, 1);
static K_SEM_DEFINE(sem_config, 0, 1);

static struct bt_conn *connection;

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static void subevent_result_cb(struct bt_conn *conn, struct bt_conn_le_cs_subevent_result *result)
{
	LOG_INF("CS Subevent result received:");
	LOG_INF(" - Procedure counter: %u", result->header.procedure_counter);
	LOG_INF(" - Procedure done status: %u", result->header.procedure_done_status);
	LOG_INF(" - Subevent done status: %u", result->header.subevent_done_status);
	LOG_INF(" - Procedure abort reason: %u", result->header.procedure_abort_reason);
	LOG_INF(" - Subevent abort reason: %u", result->header.subevent_abort_reason);
	LOG_INF(" - Reference power level: %d", result->header.reference_power_level);
	LOG_INF(" - Num antenna paths: %u", result->header.num_antenna_paths);
	LOG_INF(" - Num steps reported: %u", result->header.num_steps_reported);

	if (result->step_data_buf && result->step_data_buf->len > 0) {
		LOG_INF(" - Step data buffer length: %u bytes", result->step_data_buf->len);
		LOG_INF("Raw step data:");
		for (size_t i = 0; i < result->step_data_buf->len; i += 16) {
			printk("  ");
			for (size_t j = 0; j < 16 && (i + j) < result->step_data_buf->len; j++) {
				printk("%02x", result->step_data_buf->data[i + j]);
			}
			printk("\n");
		}
	}
	LOG_INF("CS Subevent end");
}

static void connected_cb(struct bt_conn *conn, uint8_t err)
{
	char addr[BT_ADDR_LE_STR_LEN];

	(void)bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));
	LOG_INF("Connected to %s (err 0x%02X)", addr, err);

	if (err) {
		bt_conn_unref(conn);
		connection = NULL;
	} else {
		connection = bt_conn_ref(conn);

		k_sem_give(&sem_connected);

		dk_set_led_on(CON_STATUS_LED);
	}
}

static void disconnected_cb(struct bt_conn *conn, uint8_t reason)
{
	LOG_INF("Disconnected (reason 0x%02X)", reason);

	bt_conn_unref(conn);
	connection = NULL;

	dk_set_led_off(CON_STATUS_LED);

	sys_reboot(SYS_REBOOT_COLD);
}

static void remote_capabilities_cb(struct bt_conn *conn,
				   uint8_t status,
				   struct bt_conn_le_cs_capabilities *params)
{
	ARG_UNUSED(conn);
	ARG_UNUSED(params);

	if (status == BT_HCI_ERR_SUCCESS) {
		LOG_INF("CS capability exchange completed.");
	} else {
		LOG_WRN("CS capability exchange failed. (HCI status 0x%02x)", status);
	}
}

static void config_create_cb(struct bt_conn *conn, uint8_t status,
			     struct bt_conn_le_cs_config *config)
{
	ARG_UNUSED(conn);

	if (status == BT_HCI_ERR_SUCCESS) {
		LOG_INF("CS config creation complete.");
		LOG_INF(" - id: %u", config->id);
		LOG_INF(" - mode: %u (Mode-2: PBR)", config->mode);
		LOG_INF(" - min_main_mode_steps: %u", config->min_main_mode_steps);
		LOG_INF(" - max_main_mode_steps: %u", config->max_main_mode_steps);
		LOG_INF(" - main_mode_repetition: %u", config->main_mode_repetition);
		LOG_INF(" - mode_0_steps: %u", config->mode_0_steps);
		LOG_INF(" - role: %u (Reflector)", config->role);
		LOG_INF(" - cs_sync_phy: %u", config->cs_sync_phy);
		LOG_INF(" - channel_selection_type: %u", config->channel_selection_type);

		k_sem_give(&sem_config);
	} else {
		LOG_WRN("CS config creation failed. (HCI status 0x%02x)", status);
	}
}

static void security_enable_cb(struct bt_conn *conn, uint8_t status)
{
	ARG_UNUSED(conn);

	if (status == BT_HCI_ERR_SUCCESS) {
		LOG_INF("CS security enabled.");
	} else {
		LOG_WRN("CS security enable failed. (HCI status 0x%02x)", status);
	}
}

static void procedure_enable_cb(struct bt_conn *conn,
				uint8_t status,
				struct bt_conn_le_cs_procedure_enable_complete *params)
{
	ARG_UNUSED(conn);

	if (status == BT_HCI_ERR_SUCCESS) {
		if (params->state == 1) {
			LOG_INF("CS procedures enabled:");
			LOG_INF(" - config ID: %u", params->config_id);
			LOG_INF(" - antenna configuration index: %u",
				params->tone_antenna_config_selection);
			LOG_INF(" - TX power: %d dBm", params->selected_tx_power);
			LOG_INF(" - subevent length: %u us", params->subevent_len);
			LOG_INF(" - subevents per event: %u", params->subevents_per_event);
			LOG_INF(" - subevent interval: %u", params->subevent_interval);
			LOG_INF(" - event interval: %u", params->event_interval);
			LOG_INF(" - procedure interval: %u", params->procedure_interval);
			LOG_INF(" - procedure count: %u", params->procedure_count);
			LOG_INF(" - maximum procedure length: %u", params->max_procedure_len);
		} else {
			LOG_INF("CS procedures disabled.");
		}
	} else {
		LOG_WRN("CS procedures enable failed. (HCI status 0x%02x)", status);
	}
}

BT_CONN_CB_DEFINE(conn_cb) = {
	.connected = connected_cb,
	.disconnected = disconnected_cb,
	.le_cs_read_remote_capabilities_complete = remote_capabilities_cb,
	.le_cs_config_complete = config_create_cb,
	.le_cs_security_enable_complete = security_enable_cb,
	.le_cs_procedure_enable_complete = procedure_enable_cb,
	.le_cs_subevent_data_available = subevent_result_cb,
};

int main(void)
{
	int err;

	LOG_INF("Starting Simple Channel Sounding Reflector Sample");

	dk_leds_init();

	err = bt_enable(NULL);
	if (err) {
		LOG_ERR("Bluetooth init failed (err %d)", err);
		return 0;
	}

	if (IS_ENABLED(CONFIG_BT_SETTINGS)) {
		settings_load();
	}

	err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2, ad, ARRAY_SIZE(ad), NULL, 0);
	if (err) {
		LOG_ERR("Advertising failed to start (err %d)", err);
		return 0;
	}

	LOG_INF("Advertising started. Waiting for connection...");

	while (true) {
		k_sem_take(&sem_connected, K_FOREVER);

		const struct bt_le_cs_set_default_settings_param default_settings = {
			.enable_initiator_role = false,
			.enable_reflector_role = true,
			.cs_sync_antenna_selection = BT_LE_CS_ANTENNA_SELECTION_OPT_REPETITIVE,
			.max_tx_power = BT_HCI_OP_LE_CS_MAX_MAX_TX_POWER,
		};

		err = bt_le_cs_set_default_settings(connection, &default_settings);
		if (err) {
			LOG_ERR("Failed to configure default CS settings (err %d)", err);
		}

		k_sem_take(&sem_config, K_FOREVER);

		const struct bt_le_cs_set_procedure_parameters_param procedure_params = {
			.config_id = CS_CONFIG_ID,
			.max_procedure_len = 1000,
			.min_procedure_interval = 1,
			.max_procedure_interval = 100,
			.max_procedure_count = 0,
			.min_subevent_len = 10000,
			.max_subevent_len = 75000,
			.tone_antenna_config_selection = BT_LE_CS_TONE_ANTENNA_CONFIGURATION_A1_B1,
			.phy = BT_LE_CS_PROCEDURE_PHY_2M,
			.tx_power_delta = 0x80,
			.preferred_peer_antenna = BT_LE_CS_PROCEDURE_PREFERRED_PEER_ANTENNA_1,
			.snr_control_initiator = BT_LE_CS_SNR_CONTROL_NOT_USED,
			.snr_control_reflector = BT_LE_CS_SNR_CONTROL_NOT_USED,
		};

		err = bt_le_cs_set_procedure_parameters(connection, &procedure_params);
		if (err) {
			LOG_ERR("Failed to set procedure parameters (err %d)", err);
			return 0;
		}

		LOG_INF("CS procedures configured. Waiting for results...");
	}

	return 0;
}
