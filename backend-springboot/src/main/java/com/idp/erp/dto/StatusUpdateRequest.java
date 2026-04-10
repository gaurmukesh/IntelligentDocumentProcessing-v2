package com.idp.erp.dto;

import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class StatusUpdateRequest {

    @NotNull(message = "Status is required")
    private ApplicationStatus status;

    private VerificationDecision verificationDecision;
    private Double verificationScore;
    private String decisionReason;
    private String verificationReport;
}
