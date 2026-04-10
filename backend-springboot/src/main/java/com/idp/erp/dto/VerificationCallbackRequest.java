package com.idp.erp.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * Payload received from FastAPI when document verification completes.
 * POST /api/applications/{id}/verification-result
 */
@Data
public class VerificationCallbackRequest {

    @NotBlank(message = "decision is required")
    private String decision;          // APPROVED / REJECTED / MANUAL_REVIEW

    @JsonProperty("overall_score")
    private Double overallScore;

    @JsonProperty("decision_reason")
    private String decisionReason;
}
