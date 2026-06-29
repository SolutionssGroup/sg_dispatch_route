from odoo import api, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        seller_sessions = sessions.filtered(
            lambda session: session.config_id.sg_pos_flow_role == "seller"
            and session.state == "opening_control"
        )
        if seller_sessions:
            seller_sessions.write(
                {
                    "state": "opened",
                    "start_at": fields.Datetime.now(),
                    "cash_register_balance_start": 0.0,
                }
            )
        return sessions

    def action_pos_session_open(self):
        seller_sessions = self.filtered(
            lambda session: session.config_id.sg_pos_flow_role == "seller"
            and session.state == "opening_control"
        )
        if seller_sessions:
            seller_sessions.write(
                {
                    "state": "opened",
                    "start_at": fields.Datetime.now(),
                    "cash_register_balance_start": 0.0,
                }
            )
        remaining_sessions = self - seller_sessions
        if remaining_sessions:
            return super(PosSession, remaining_sessions).action_pos_session_open()
        return True

    def action_pos_session_closing_control(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ):
        seller_sessions = self.filtered(lambda session: session.config_id.sg_pos_flow_role == "seller")
        for session in seller_sessions:
            if session.state != "closed":
                session.write({"state": "closing_control", "stop_at": fields.Datetime.now()})
                session.action_pos_session_close(
                    balancing_account,
                    amount_to_balance,
                    bank_payment_method_diffs,
                )

        remaining_sessions = self - seller_sessions
        if remaining_sessions:
            return super(PosSession, remaining_sessions).action_pos_session_closing_control(
                balancing_account,
                amount_to_balance,
                bank_payment_method_diffs,
            )
        return True

    def _get_pos_ui_pos_config(self, params):
        config = super()._get_pos_ui_pos_config(params)
        config["sg_pos_flow_role"] = self.config_id.sg_pos_flow_role
        if self.config_id.sg_pos_flow_role == "seller":
            config["cash_control"] = False
        return config
