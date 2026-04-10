from app.services.algo_package_service import run_active_package
from app.services.builtin_algo_packages import bootstrap_builtin_algo_packages


VIP_MANAGEMENT_TEXT = (
    "\u5bf9\u534e\u82f1\u516c\u53f8\u8425\u8fd0\u8d44\u91d1\u7ba1\u7406\u8fdb\u884c\u7814\u7a76\uff0c"
    "\u4ece\u6d41\u52a8\u8d44\u4ea7\u3001\u6d41\u52a8\u8d1f\u503a\u3001\u5b58\u8d27\u7ba1\u7406\u4ee5\u53ca"
    "\u73b0\u91d1\u7ba1\u7406\u56db\u4e2a\u65b9\u9762\u8fdb\u884c\u5206\u6790\u3002"
    "\u5e76\u7ed3\u5408\u534e\u82f1\u516c\u53f8\u5f53\u524d\u8425\u8fd0\u8d44\u91d1\u5b58\u5728\u7684\u95ee\u9898\uff0c"
    "\u63d0\u51fa\u76f8\u5e94\u7684\u89e3\u51b3\u5bf9\u7b56\uff0c\u4ee5\u63d0\u9ad8\u8425\u8fd0\u8d44\u91d1\u7ba1\u7406\u6c34\u5e73\u3002"
)


VIP_CASE_TEXT = (
    "\u8bba\u6587\u4ece\u8425\u8fd0\u8d44\u91d1\u7684\u5206\u6790\u5f00\u59cb\uff0c"
    "\u79c9\u6301\u201c\u5206\u6790\u73b0\u72b6--\u53d1\u73b0\u95ee\u9898--\u89e3\u51b3\u95ee\u9898\u201d\u7684\u601d\u8def\u3002"
    "\u4e0a\u6d77\u4e2d\u5fc3\u5927\u53a6\u4f4d\u4e8e\u4e0a\u6d77\u6d66\u4e1c\u65b0\u533a\u9646\u5bb6\u5634\u91d1\u878d\u4e2d\u5fc3Z3-1\u3001Z3-2\u5730\u5757\uff0c"
    "\u5360\u5730\u9762\u79ef30368\u5e73\u65b9\u7c73\uff0c\u5efa\u7b51\u9762\u79ef574058\u4e07\u5e73\u65b9\u7c73\u3002"
    "\u8be5\u9879\u76ee\u5305\u62ec\u5730\u4e0b\u4e94\u5c42\u7684\u5730\u5e93\u3001"
    "\u4e00\u5e62121\u5c42\u9ad8\u7684\u7efc\u5408\u697c\u548c\u4e00\u5e62\u4e94\u5c42\u9ad8\u7684\u5546\u4e1a\u88d9\u697c\u3002"
)


def test_vip_builtin_dedup_package_rewrites_management_thesis_frames(
    db_session,
    settings_override,
) -> None:
    bootstrap_builtin_algo_packages(db_session, uploaded_by=1, activate_after_upload=True)

    result, _meta = run_active_package(
        db_session,
        platform="vip",
        function_type="dedup",
        text=VIP_MANAGEMENT_TEXT,
    )

    assert isinstance(result, dict)
    assert result["algorithm"] == "vip_dedup_sim_v1_2_1"
    assert result["changes"] >= 3
    assert result["rewritten_risk_score"] < result["original_risk_score"]
    assert "management_analysis" in result["focus_flags"]
    assert "围绕华英公司营运资金管理展开讨论" in result["text"]
    assert "方面加以拆解" in result["text"]
    assert "进一步细化改进对策" in result["text"]
    assert "以带动营运资金管理效能提升" in result["text"]
    assert "提出相应的解决对策" not in result["text"]
    assert "以提高营运资金管理水平" not in result["text"]


def test_vip_builtin_dedup_package_rewrites_case_fact_segments(
    db_session,
    settings_override,
) -> None:
    bootstrap_builtin_algo_packages(db_session, uploaded_by=1, activate_after_upload=True)

    result, _meta = run_active_package(
        db_session,
        platform="vip",
        function_type="dedup",
        text=VIP_CASE_TEXT,
    )

    assert isinstance(result, dict)
    assert result["algorithm"] == "vip_dedup_sim_v1_2_1"
    assert result["changes"] >= 3
    assert result["rewritten_risk_score"] < result["original_risk_score"]
    assert "thesis_frame" in result["focus_flags"]
    assert "case_fact" in result["focus_flags"]
    assert "文章先梳理营运资金现状，再归纳问题表现，随后承接改进思路" in result["text"]
    assert "上海中心大厦坐落于上海浦东新区陆家嘴金融中心Z3-1、Z3-2地块" in result["text"]
    assert "项目建设内容涵盖地下五层的地库" in result["text"]
    assert "分析现状--发现问题--解决问题" not in result["text"]
