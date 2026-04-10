package com.idp.erp.dto;

import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data @Builder
public class ApplicationResponse {
    private String id;
    private String studentId;
    private String studentName;
    private String courseApplied;
    private ApplicationStatus status;
    private VerificationDecision verificationDecision;
    private Double verificationScore;
    private String decisionReason;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
