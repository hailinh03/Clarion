"""
Clarion — Coverage Check Service
Tính cosine similarity giữa AC/BR/EC vectors và test case vectors.
Ngưỡng đọc từ env COVERAGE_THRESHOLD (default 0.75).
"""
import os
import numpy as np
from typing import List, Dict, Any, Optional

from app.services.embedding import embed_batch
from app.schemas.testcase import TestCase

def _calculate_coverage_for_list(
    requirement_list: List[str],
    tc_vectors: np.ndarray,
    threshold: float,
    requirement_type: str = "AC"
) -> Dict[str, Any]:
    """
    Tính coverage cho một danh sách requirements (AC/BR/EC).
    
    Args:
        requirement_list: Danh sách AC/BR/EC
        tc_vectors: Matrix của test case vectors (n_test_cases, embedding_dim)
        threshold: Ngưỡng similarity
        requirement_type: Loại requirement ("AC", "BR", "EC")
    
    Returns:
        Dict gồm coverage_percentage, covered, gaps
    """
    if not requirement_list:
        return {
            "type": requirement_type,
            "coverage_percentage": 0.0,
            "total": 0,
            "covered_count": 0,
            "gaps": [],
            "covered": []
        }
    
    # Lọc bỏ requirement rỗng
    valid_reqs = [req for req in requirement_list if req.strip()]
    if not valid_reqs:
        return {
            "type": requirement_type,
            "coverage_percentage": 100.0,
            "total": 0,
            "covered_count": 0,
            "gaps": [],
            "covered": []
        }
    
    req_vectors = np.array(embed_batch(valid_reqs))
    
    # Calculate cosine similarity matrix (dot product since L2 normalized)
    sim_matrix = np.dot(req_vectors, tc_vectors.T)
    
    gaps = []
    covered = []
    
    for i, req in enumerate(valid_reqs):
        max_sim = np.max(sim_matrix[i])
        if max_sim < threshold:
            gaps.append(req)
        else:
            covered.append(req)
    
    coverage_percentage = round(len(covered) / len(valid_reqs) * 100, 2)
    
    return {
        "type": requirement_type,
        "coverage_percentage": coverage_percentage,
        "total": len(valid_reqs),
        "covered_count": len(covered),
        "gaps": gaps,
        "covered": covered
    }

def coverage_check(
    ac_list: List[str],
    test_cases: List[TestCase],
    br_list: Optional[List[str]] = None,
    ec_list: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Kiểm tra coverage của test case đối với AC, BR, và EC.
    
    Args:
        ac_list: Danh sách Acceptance Criteria
        test_cases: Danh sách TestCase đã sinh
        br_list: Danh sách Business Rules (optional)
        ec_list: Danh sách Edge Cases (optional)
    
    Returns:
        Dict gồm:
        - ac_coverage: coverage report cho AC
        - br_coverage: coverage report cho BR (nếu có)
        - ec_coverage: coverage report cho EC (nếu có)
        - overall_coverage_percentage: % coverage chung (trung bình weighted)
        - total_requirements: tổng số requirement
        - total_covered: tổng số requirement được cover
    """
    threshold = float(os.getenv("COVERAGE_THRESHOLD", "0.75"))
    
    if not ac_list or not test_cases:
        return {
            "ac_coverage": {
                "type": "AC",
                "coverage_percentage": 0.0,
                "total": len(ac_list),
                "covered_count": 0,
                "gaps": ac_list,
                "covered": []
            },
            "br_coverage": {
                "type": "BR",
                "coverage_percentage": 0.0,
                "total": len(br_list) if br_list else 0,
                "covered_count": 0,
                "gaps": br_list if br_list else [],
                "covered": []
            } if br_list else None,
            "ec_coverage": {
                "type": "EC",
                "coverage_percentage": 0.0,
                "total": len(ec_list) if ec_list else 0,
                "covered_count": 0,
                "gaps": ec_list if ec_list else [],
                "covered": []
            } if ec_list else None,
            "overall_coverage_percentage": 0.0,
            "total_requirements": len(ac_list) + (len(br_list) if br_list else 0) + (len(ec_list) if ec_list else 0),
            "total_covered": 0
        }
    
    # Embed test case texts
    tc_texts = [f"{tc.title} {' '.join(tc.steps)}" for tc in test_cases]
    tc_vectors = np.array(embed_batch(tc_texts))
    
    # Calculate coverage cho từng loại
    ac_coverage = _calculate_coverage_for_list(ac_list, tc_vectors, threshold, "AC")
    br_coverage = _calculate_coverage_for_list(br_list or [], tc_vectors, threshold, "BR") if br_list else None
    ec_coverage = _calculate_coverage_for_list(ec_list or [], tc_vectors, threshold, "EC") if ec_list else None
    
    # Tính overall coverage (trung bình weighted)
    total_requirements = ac_coverage["total"] + (br_coverage["total"] if br_coverage else 0) + (ec_coverage["total"] if ec_coverage else 0)
    total_covered = ac_coverage["covered_count"] + (br_coverage["covered_count"] if br_coverage else 0) + (ec_coverage["covered_count"] if ec_coverage else 0)
    
    overall_coverage_percentage = 0.0
    if total_requirements > 0:
        overall_coverage_percentage = round(total_covered / total_requirements * 100, 2)
    
    return {
        "ac_coverage": ac_coverage,
        "br_coverage": br_coverage,
        "ec_coverage": ec_coverage,
        "overall_coverage_percentage": overall_coverage_percentage,
        "total_requirements": total_requirements,
        "total_covered": total_covered
    }
