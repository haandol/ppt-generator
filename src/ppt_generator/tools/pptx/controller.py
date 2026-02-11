from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ExportPptxRequest
from ppt_generator.tools.pptx.service import ExportService


def register_pptx_tools(mcp: FastMCP, export_service: ExportService) -> None:
    @mcp.tool()
    def export_pptx(session_id: str) -> str:
        """세션의 최종 HTML 슬라이드를 편집 가능한 PPTX 파일로 내보냅니다.

        generate_slides로 생성된 HTML 세션을 파싱하여, 텍스트/이미지/도형이
        개별 객체로 분리된 편집 가능한 PPTX 파일로 변환합니다.
        modify_slides로 수정한 내용도 반영됩니다.

        Args:
            session_id: generate_slides가 반환한 세션 ID

        Returns:
            생성된 .pptx 파일 경로
        """
        request = ExportPptxRequest(session_id=session_id)
        response = export_service.export(request)
        return response.pptx_path
