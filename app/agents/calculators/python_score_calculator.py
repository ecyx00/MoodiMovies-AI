"""
Python based implementation of Big Five T-score calculator.
Implements 6-step methodology for calculation of T-scores.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from collections import defaultdict
from loguru import logger
import math

from app.agents.common.interfaces import IScoreCalculator
from app.schemas.personality import ResponseDataItem
from app.core.config import Settings


class PythonScoreCalculator(IScoreCalculator):
    """
    Calculator that computes Big Five personality T-scores from test responses
    using Python's Decimal type for precise calculations.
    
    Implements 6-step methodology:
    1. Group responses by facet and adjust scores (reverse scoring)
    2. Calculate facet mean raw scores
    3. Calculate z-scores for facets
    4. Convert z-scores to T-scores (mean 50, std 10)
    5. Calculate domain scores as averages of facet T-scores
    6. Format output in the required structure
    """

    # Class-level constants
    EXPECTED_DOMAINS: set = {"O", "C", "E", "A", "N"}  # Database/internal format (uppercase)
    API_DOMAINS: set = {"o", "c", "e", "a", "n"}  # API v1.2 format (lowercase)
    EXPECTED_FACETS_PER_DOMAIN: int = 6
    T_SCORE_MEAN: Decimal = Decimal(50)
    T_SCORE_STD_DEV: Decimal = Decimal(10)
    ROUNDING_PRECISION: Decimal = Decimal("0.01")
    ROUNDING_METHOD = ROUND_HALF_UP
    
    def __init__(self, settings: Settings):
        """
        Initialize the Python score calculator with settings.
        
        Args:
            settings: Application settings containing personality calculation parameters
        """
        self.settings = settings
        
        # Convert mean and std_dev to Decimal for precise calculations
        self.personality_mean = Decimal(str(settings.PERSONALITY_MEAN))
        self.personality_std_dev = Decimal(str(settings.PERSONALITY_STD_DEV))
        
        # Validate standard deviation is not zero to avoid division by zero
        if self.personality_std_dev == Decimal(0):
            logger.error("Personality standard deviation cannot be zero")
            raise ValueError("Personality standard deviation cannot be zero.")
            
        logger.info(
            f"Initialized PythonScoreCalculator with mean={self.personality_mean}, "
            f"std_dev={self.personality_std_dev}"
        )
    
    async def calculate_scores(self, responses: List[ResponseDataItem]) -> Dict[str, Any]:
        """
        Calculate personality T-scores from test responses.
        
        Args:
            responses: List of response data items from the personality test
            
        Returns:
            Dictionary containing domain scores and facet scores in the format (v1.2 API):
            {
                'o': Decimal, 'c': Decimal, 'e': Decimal, 'a': Decimal, 'n': Decimal,
                'facets': {
                    'o_f1': Decimal, 'o_f2': Decimal, ..., 'n_f6': Decimal
                }
            }
        """
        try:
            logger.info(f"Calculating personality scores for {len(responses)} responses")
            
            # Step 1: Group responses by facet and adjust scores
            facet_adjusted_scores = self._group_and_adjust_scores(responses)
            
            # Step 2: Calculate facet mean raw scores
            raw_facet_scores = self._calculate_facet_means(facet_adjusted_scores)
            
            # Step 3: Calculate z-scores
            facet_z_scores = self._calculate_z_scores(raw_facet_scores)
            
            # Step 4: Calculate T-scores
            facet_t_scores = self._calculate_t_scores(facet_z_scores)
            
            # Step 5: Calculate domain means
            domain_t_scores = self._calculate_domain_means(facet_t_scores)
            
            # Step 6: Format output
            final_result = self._format_output(domain_t_scores, facet_t_scores)
            
            logger.info("Successfully calculated personality scores")
            return final_result
            
        except Exception as e:
            logger.error(f"Error calculating personality scores: {e}")
            raise ValueError(f"Score calculation failed: {str(e)}") from e
    
    def _group_and_adjust_scores(self, responses: List[ResponseDataItem]) -> Dict[str, List[Decimal]]:
        """
        Step 1: Group responses by facet code and adjust scores.
        
        For reverse-scored items, compute 6 - point.
        For normal-scored items, use point directly.
        
        Args:
            responses: List of response data items
            
        Returns:
            Dictionary mapping facet codes to lists of adjusted decimal scores
        """
        facet_adjusted_scores: Dict[str, List[Decimal]] = defaultdict(list)
        
        for resp in responses:
            if resp.point is None:
                logger.warning(f"Skipping response with NULL point value for facet {resp.facet_code}")
                continue
                
            try:
                point_decimal = Decimal(str(resp.point))
                
                # Adjust score if reverse scored
                if resp.reverse_scored:
                    adjusted_score = Decimal(6) - point_decimal
                else:
                    adjusted_score = point_decimal
                
                # Validate score is in expected range
                if adjusted_score < Decimal(1) or adjusted_score > Decimal(5):
                    logger.warning(
                        f"Adjusted score {adjusted_score} for facet {resp.facet_code} "
                        f"is outside expected range [1-5]"
                    )
                    continue
                    
                # Add to appropriate facet group
                if resp.facet_code:
                    facet_adjusted_scores[resp.facet_code].append(adjusted_score)
                else:
                    logger.warning("Response has no facet code, skipping")
                    
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing response point value: {e}")
                continue
                
        logger.debug(f"Grouped responses into {len(facet_adjusted_scores)} facets")
        return facet_adjusted_scores
    
    def _calculate_facet_means(self, facet_adjusted_scores: Dict[str, List[Decimal]]) -> Dict[str, Decimal]:
        """
        Step 2: Calculate mean raw scores for each facet.
        
        Args:
            facet_adjusted_scores: Dictionary mapping facet codes to lists of adjusted scores
            
        Returns:
            Dictionary mapping facet codes to mean raw scores
        """
        raw_facet_scores: Dict[str, Decimal] = {}
        
        # Generate all 30 facet codes
        all_facet_codes = [f"{domain}_F{i}" for domain in self.EXPECTED_DOMAINS 
                           for i in range(1, self.EXPECTED_FACETS_PER_DOMAIN + 1)]
        
        for facet_code in all_facet_codes:
            scores_list = facet_adjusted_scores.get(facet_code, [])
            
            if scores_list:
                # Calculate mean if there are scores
                mean_score = sum(scores_list) / Decimal(len(scores_list))
            else:
                # Use population mean if no scores
                logger.warning(f"No responses for facet {facet_code}, using population mean")
                mean_score = self.personality_mean
                
            raw_facet_scores[facet_code] = mean_score
            logger.debug(f"Facet {facet_code} raw score: {mean_score}")
            
        return raw_facet_scores
    
    def _calculate_z_scores(self, raw_facet_scores: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Step 3: Calculate z-scores for each facet.
        
        z-score = (raw_score - population_mean) / population_std_dev
        
        Args:
            raw_facet_scores: Dictionary mapping facet codes to mean raw scores
            
        Returns:
            Dictionary mapping facet codes to z-scores
        """
        facet_z_scores: Dict[str, Decimal] = {}
        
        for facet_code, raw_score in raw_facet_scores.items():
            z_score = (raw_score - self.personality_mean) / self.personality_std_dev
            facet_z_scores[facet_code] = z_score
            logger.debug(f"Facet {facet_code} z-score: {z_score}")
            
        return facet_z_scores
    
    def _calculate_t_scores(self, facet_z_scores: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Step 4: Calculate T-scores for each facet.
        
        T-score = 50 + (10 * z-score)
        
        Args:
            facet_z_scores: Dictionary mapping facet codes to z-scores
            
        Returns:
            Dictionary mapping facet codes to rounded T-scores
        """
        facet_t_scores: Dict[str, Decimal] = {}
        
        for facet_code, z_score in facet_z_scores.items():
            t_score_raw = self.T_SCORE_MEAN + (self.T_SCORE_STD_DEV * z_score)
            t_score_rounded = t_score_raw.quantize(self.ROUNDING_PRECISION, rounding=self.ROUNDING_METHOD)
            facet_t_scores[facet_code] = t_score_rounded
            logger.debug(f"Facet {facet_code} T-score: {t_score_rounded}")
            
        return facet_t_scores
    
    def _calculate_domain_means(self, facet_t_scores: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Step 5: Calculate mean T-scores for each domain.
        
        Args:
            facet_t_scores: Dictionary mapping facet codes to T-scores
            
        Returns:
            Dictionary mapping domain codes to rounded T-scores
        """
        domain_t_scores: Dict[str, Decimal] = {}
        
        for domain in self.EXPECTED_DOMAINS:
            # Generate the 6 facet codes for this domain
            domain_facet_codes = [f"{domain}_F{i}" for i in range(1, self.EXPECTED_FACETS_PER_DOMAIN + 1)]
            
            # Get the T-scores for the facets of this domain
            relevant_facet_scores = [facet_t_scores.get(code) for code in domain_facet_codes 
                                    if code in facet_t_scores]
            
            # Ensure all 6 facets have scores
            if len(relevant_facet_scores) == self.EXPECTED_FACETS_PER_DOMAIN:
                domain_mean_raw = sum(relevant_facet_scores) / Decimal(self.EXPECTED_FACETS_PER_DOMAIN)
                domain_mean_rounded = domain_mean_raw.quantize(
                    self.ROUNDING_PRECISION, rounding=self.ROUNDING_METHOD
                )
                domain_t_scores[domain] = domain_mean_rounded
                logger.debug(f"Domain {domain} T-score: {domain_mean_rounded}")
            else:
                error_msg = f"Domain {domain} has {len(relevant_facet_scores)} facets with scores, expected 6"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        return domain_t_scores
    
    def _format_output(self, domain_t_scores: Dict[str, Decimal], 
                       facet_t_scores: Dict[str, Decimal]) -> Dict[str, Any]:
        """
        Step 6: Format output in the required structure with lowercase keys (v1.2 API).
        
        Args:
            domain_t_scores: Dictionary mapping domain codes to T-scores (uppercase keys)
            facet_t_scores: Dictionary mapping facet codes to T-scores (uppercase keys)
            
        Returns:
            Dictionary with domain scores at the top level and facet scores in a 'facets' sub-dictionary,
            all using lowercase keys as per v1.2 API specification
        """
        # Convert domain keys to lowercase for API v1.2 format
        # Example: 'O' -> 'o', 'C' -> 'c', etc.
        lowercase_domain_scores = {k.lower(): v for k, v in domain_t_scores.items()}
        
        # Convert facet keys to lowercase for API v1.2 format
        # Example: 'O_F1' -> 'o_f1', 'C_F2' -> 'c_f2', etc.
        lowercase_facet_scores = {}
        for k, v in facet_t_scores.items():
            # Split domain and facet part (e.g., 'O_F1' -> 'O', 'F1')
            parts = k.split('_')
            # Reconstruct with lowercase (e.g., 'o_f1')
            lowercase_key = f"{parts[0].lower()}_{parts[1].lower()}"
            lowercase_facet_scores[lowercase_key] = v
        
        # Create the final result with lowercase domain scores
        final_result = lowercase_domain_scores
        
        # Add lowercase facet scores under 'facets' key
        final_result["facets"] = lowercase_facet_scores
        
        logger.debug(f"Formatted output with lowercase keys for API v1.2 format")
        return final_result
