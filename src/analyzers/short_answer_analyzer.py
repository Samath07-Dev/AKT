"""
src/analyzers/short_answer_analyzer.py

Short Answer Response Analyzer for Natural Language Conceptual Questions.
Uses sentence-transformers/all-MiniLM-L6-v2 to compute semantic embeddings,
calculates cosine similarity against reference answer rubrics,
and strictly bounds the resulting score to [0.0, 1.0].
"""

import numpy as np
from typing import Dict, Any, Optional

class ShortAnswerAnalyzer:
    """
    Analyzes natural language short answer responses using Sentence Transformers.
    Computes semantic similarity against standard answer rubrics and clamps scores to [0.0, 1.0].
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initializes the SentenceTransformer model with graceful fallback handling."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            print(f"ShortAnswerAnalyzer: Successfully loaded transformer model '{self.model_name}'")
        except Exception as e:
            print(f"ShortAnswerAnalyzer: Warning - Could not load transformer '{self.model_name}': {e}")
            print("  -> Falling back to lightweight lexical token similarity.")
            self.model = None

    def compute_cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Computes cosine similarity between two vector embeddings u and v:
        sim = (u . v) / (||u|| * ||v||)
        Strictly bounded to [0.0, 1.0].
        """
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        sim = float(np.dot(emb1, emb2) / (norm1 * norm2))
        # Clamp cosine similarity strictly to [0.0, 1.0] interval
        bounded_sim = float(np.clip(sim, 0.0, 1.0))
        return bounded_sim

    def _fallback_lexical_similarity(self, text1: str, text2: str) -> float:
        """Fallback word-overlap Jaccard similarity when transformer model is offline."""
        tokens1 = set(str(text1).lower().split())
        tokens2 = set(str(text2).lower().split())
        
        if not tokens1 or not tokens2:
            return 0.0
            
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        sim = float(intersection / max(union, 1))
        return float(np.clip(sim, 0.0, 1.0))

    STOP_WORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 'when',
        'where', 'how', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
        'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'having', 'do', 'does', 'did', 'doing', 'at', 'by', 'for', 'with', 'about',
        'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'all', 'any', 'both',
        'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will',
        'just', 'should', 'now', 'its', 'their', 'our', 'your', 'my', 'his', 'her',
        'used', 'also', 'such', 'into', 'well'
    }

    def extract_missing_keywords(self, student_response: str, reference_answer: str) -> list:
        """
        Extracts key conceptual terms from the reference answer that are missing in the student response.
        """
        import re
        if not reference_answer:
            return []
        
        # Tokenize words >= 4 letters
        ref_tokens = re.findall(r'\b[a-zA-Z_]{4,}\b', reference_answer.lower())
        student_text = str(student_response).lower()

        seen = set()
        missing = []
        for word in ref_tokens:
            if word not in self.STOP_WORDS and word not in seen:
                seen.add(word)
                stem = word[:-1] if word.endswith(('s', 'e', 'd')) and len(word) > 4 else word
                if stem not in student_text and word not in student_text:
                    missing.append(word)

        return missing[:6]

    def evaluate(
        self,
        student_response: str,
        reference_answer: str,
        min_similarity_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Evaluates student short answer text response against target reference answer.
        
        Parameters:
        - student_response: Text written by student
        - reference_answer: Ground truth reference answer / grading rubric text
        - min_similarity_threshold: Minimum similarity threshold for feedback
        
        Returns:
        - Dict with 'evidence_score' (0.0 to 1.0), 'similarity_percentage', 'missing_keywords', and feedback metadata.
        """
        missing_keywords = self.extract_missing_keywords(student_response, reference_answer)

        if not student_response or not str(student_response).strip():
            return {
                "evidence_score": 0.0,
                "similarity_percentage": 0.0,
                "cosine_similarity": 0.0,
                "missing_keywords": missing_keywords,
                "feedback": "Empty student response.",
                "model_used": "none"
            }

        if not reference_answer or not str(reference_answer).strip():
            return {
                "evidence_score": 0.0,
                "similarity_percentage": 0.0,
                "cosine_similarity": 0.0,
                "missing_keywords": [],
                "feedback": "Missing reference answer for grading.",
                "model_used": "none"
            }

        if self.model is not None:
            try:
                # Encode text responses into 384-dimensional dense semantic vectors
                embeddings = self.model.encode([student_response, reference_answer], convert_to_numpy=True)
                emb_student = embeddings[0]
                emb_ref = embeddings[1]

                raw_sim = self.compute_cosine_similarity(emb_student, emb_ref)
                model_used = self.model_name
            except Exception as e:
                raw_sim = self._fallback_lexical_similarity(student_response, reference_answer)
                model_used = f"lexical_fallback ({e})"
        else:
            raw_sim = self._fallback_lexical_similarity(student_response, reference_answer)
            model_used = "lexical_fallback"

        # Ensure evidence score is strictly bounded to [0.0, 1.0]
        evidence_score = float(np.clip(raw_sim, 0.0, 1.0))
        similarity_percentage = round(evidence_score * 100.0, 1)
        is_acceptable = evidence_score >= min_similarity_threshold

        return {
            "evidence_score": evidence_score,
            "similarity_percentage": similarity_percentage,
            "cosine_similarity": raw_sim,
            "missing_keywords": missing_keywords,
            "is_acceptable": is_acceptable,
            "model_used": model_used,
            "feedback": f"Semantic Similarity Score: {similarity_percentage:.1f}%"
        }
