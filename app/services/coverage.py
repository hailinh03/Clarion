"""
Clarion — Coverage Check Service
Tính cosine similarity giữa AC vectors và test case vectors.
Ngưỡng đọc từ env COVERAGE_THRESHOLD (default 0.75).
"""
import os
import numpy as np
from typing import List, Dict, Any

from app.services.embedding import embed_batch
from app.schemas.testcase import TestCase

def coverage_check(ac_list: List[str], test_cases: List[TestCase]) -> Dict[str, Any]:
    threshold = float(os.getenv("COVERAGE_THRESHOLD", "0.75"))
    
    if not ac_list or not test_cases:
        return {
            "coverage_percentage": 0.0,
            "gaps": ac_list,
            "covered": []
        }
        
    # Lọc bỏ AC rỗng
    valid_acs = [ac for ac in ac_list if ac.strip()]
    if not valid_acs:
        return {"coverage_percentage": 100.0, "gaps": [], "covered": []}
        
    ac_vectors = np.array(embed_batch(valid_acs))
    
    tc_texts = [f"{tc.title} {' '.join(tc.steps)}" for tc in test_cases]
    tc_vectors = np.array(embed_batch(tc_texts))
    
    # Calculate cosine similarity matrix (dot product since L2 normalized)
    sim_matrix = np.dot(ac_vectors, tc_vectors.T)
    
    gaps = []
    covered = []
    
    for i, ac in enumerate(valid_acs):
        max_sim = np.max(sim_matrix[i])
        if max_sim < threshold:
            gaps.append(ac)
        else:
            covered.append(ac)
            
    coverage_percentage = round(len(covered) / len(valid_acs) * 100, 2)
    
    return {
        "coverage_percentage": coverage_percentage,
        "gaps": gaps,
        "covered": covered
    }
