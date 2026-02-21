"""Tool Approval Dialog - Team 3: Tool Approval System

Interactive UI for approving or rejecting tool executions.
Shows risk assessment and allows user to make informed decisions.
"""

import streamlit as st
from typing import Optional
import json
import logging

from lib.tool_interceptor import tool_interceptor, ToolCall
from lib.security_analyzer import security_analyzer
from lib.audit_logger import audit_logger

logger = logging.getLogger(__name__)


def render_tool_approval_dialog():
    """Render tool approval dialog for pending tools."""
    # Get pending tools
    pending_tools = tool_interceptor.get_pending()

    if not pending_tools:
        st.info("No pending tool approvals")
        return

    st.warning(f"{len(pending_tools)} tool(s) awaiting approval")

    # Display each pending tool
    for tool_call in pending_tools:
        render_tool_approval_card(tool_call)


def render_tool_approval_card(tool_call: ToolCall):
    """Render approval card for a single tool call.

    Args:
        tool_call: ToolCall to display
    """
    # Perform security analysis
    assessment = security_analyzer.analyze(tool_call.tool_name, tool_call.parameters)

    # Create expander for this tool
    risk_label = security_analyzer.get_risk_label(assessment.risk_score)
    risk_emoji = {
        "Low Risk": "🟢",
        "Medium Risk": "🟡",
        "High Risk": "🟠",
        "Critical Risk": "🔴"
    }.get(risk_label, "⚪")

    with st.expander(
        f"{risk_emoji} {tool_call.tool_name} - {risk_label}",
        expanded=True
    ):
        # Tool details
        st.subheader("Tool Details")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Tool", tool_call.tool_name)

        with col2:
            st.metric("Danger Level", tool_call.danger_level.name)

        with col3:
            st.metric("Risk Score", f"{assessment.risk_score}/100")

        # Parameters
        st.subheader("Parameters")
        st.json(tool_call.parameters)

        # Risk assessment
        st.divider()
        st.subheader("Risk Assessment")

        # Risk categories
        if assessment.risk_categories:
            st.write("Risk Categories:")
            for category in assessment.risk_categories:
                st.markdown(f"- {category.value.replace('_', ' ').title()}")

        # Warnings
        if assessment.warnings:
            st.warning("Warnings:")
            for warning in assessment.warnings:
                st.markdown(f"- {warning}")

        # Recommendations
        if assessment.recommendations:
            st.info("Recommendations:")
            for rec in assessment.recommendations:
                st.markdown(f"- {rec}")

        # Approval decision
        st.divider()
        st.subheader("Decision")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Approve", key=f"approve_{tool_call.id}", type="primary", use_container_width=True):
                approve_tool(tool_call)
                st.rerun()

        with col2:
            if st.button("Reject", key=f"reject_{tool_call.id}", type="secondary", use_container_width=True):
                # Show rejection reason input
                st.session_state[f"reject_reason_{tool_call.id}"] = True

        with col3:
            if st.button("Modify Parameters", key=f"modify_{tool_call.id}", use_container_width=True):
                st.session_state[f"modify_{tool_call.id}"] = True

        # Rejection reason input
        if st.session_state.get(f"reject_reason_{tool_call.id}", False):
            reason = st.text_input(
                "Rejection reason:",
                key=f"reason_input_{tool_call.id}",
                placeholder="Why are you rejecting this tool?"
            )
            if st.button("Confirm Rejection", key=f"confirm_reject_{tool_call.id}"):
                reject_tool(tool_call, reason)
                st.session_state[f"reject_reason_{tool_call.id}"] = False
                st.rerun()

        # Parameter modification
        if st.session_state.get(f"modify_{tool_call.id}", False):
            st.write("Edit parameters (JSON):")
            modified_params = st.text_area(
                "Parameters:",
                value=json.dumps(tool_call.parameters, indent=2),
                key=f"params_edit_{tool_call.id}",
                height=150
            )

            if st.button("Apply Changes", key=f"apply_changes_{tool_call.id}"):
                try:
                    new_params = json.loads(modified_params)
                    tool_call.parameters = new_params
                    st.success("Parameters updated")
                    st.session_state[f"modify_{tool_call.id}"] = False
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")


def approve_tool(tool_call: ToolCall):
    """Approve a tool call.

    Args:
        tool_call: ToolCall to approve
    """
    try:
        # Get current user (default to "streamlit_user")
        approver = st.session_state.get('username', 'streamlit_user')

        # Approve in interceptor
        success = tool_interceptor.approve(tool_call.id, approver)

        if success:
            st.success(f"Approved: {tool_call.tool_name}")

            # Log to audit
            audit_logger.log_approval(
                tool_name=tool_call.tool_name,
                parameters=tool_call.parameters,
                approver=approver,
                approved=True
            )

    except Exception as e:
        logger.error(f"Error approving tool: {e}")
        st.error(f"Failed to approve: {e}")


def reject_tool(tool_call: ToolCall, reason: str = ""):
    """Reject a tool call.

    Args:
        tool_call: ToolCall to reject
        reason: Reason for rejection
    """
    try:
        # Get current user
        approver = st.session_state.get('username', 'streamlit_user')

        # Reject in interceptor
        success = tool_interceptor.reject(tool_call.id, approver, reason)

        if success:
            st.warning(f"Rejected: {tool_call.tool_name}")

            # Log to audit
            audit_logger.log_approval(
                tool_name=tool_call.tool_name,
                parameters=tool_call.parameters,
                approver=approver,
                approved=False,
                reason=reason
            )

    except Exception as e:
        logger.error(f"Error rejecting tool: {e}")
        st.error(f"Failed to reject: {e}")


def render_approval_history():
    """Render history of approved/rejected tools."""
    st.subheader("Approval History")

    tab1, tab2 = st.tabs(["Approved", "Rejected"])

    with tab1:
        approved = list(tool_interceptor.approved_calls.values())

        if approved:
            for tool_call in approved:
                with st.expander(f"✅ {tool_call.tool_name} - {tool_call.timestamp.strftime('%H:%M:%S')}"):
                    st.json({
                        "tool": tool_call.tool_name,
                        "approver": tool_call.approver,
                        "parameters": tool_call.parameters,
                        "executed": tool_call.executed
                    })
        else:
            st.info("No approved tools yet")

    with tab2:
        rejected = list(tool_interceptor.rejected_calls.values())

        if rejected:
            for tool_call in rejected:
                with st.expander(f"❌ {tool_call.tool_name} - {tool_call.timestamp.strftime('%H:%M:%S')}"):
                    st.json({
                        "tool": tool_call.tool_name,
                        "approver": tool_call.approver,
                        "reason": tool_call.rejection_reason,
                        "parameters": tool_call.parameters
                    })
        else:
            st.info("No rejected tools yet")


def render_approval_settings():
    """Render settings for approval system."""
    st.subheader("Approval Settings")

    # Auto-approve safe tools
    auto_approve = st.checkbox(
        "Auto-approve safe tools",
        value=st.session_state.get('auto_approve_safe', False),
        help="Automatically approve tools with SAFE danger level"
    )

    st.session_state['auto_approve_safe'] = auto_approve

    if auto_approve:
        count = tool_interceptor.auto_approve_safe()
        if count > 0:
            st.success(f"Auto-approved {count} safe tools")

    # Require reason for rejection
    require_reason = st.checkbox(
        "Require rejection reason",
        value=st.session_state.get('require_rejection_reason', True)
    )

    st.session_state['require_rejection_reason'] = require_reason

    # Show risk assessment
    show_risk = st.checkbox(
        "Show detailed risk assessment",
        value=st.session_state.get('show_risk_assessment', True)
    )

    st.session_state['show_risk_assessment'] = show_risk
