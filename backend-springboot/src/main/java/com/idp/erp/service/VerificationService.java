package com.idp.erp.service;

import com.idp.erp.client.AiServiceClient;
import com.idp.erp.dto.VerificationCallbackRequest;
import com.idp.erp.entity.Application;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import com.idp.erp.repository.ApplicationRepository;
import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Orchestrates verification between Spring Boot ERP and the FastAPI AI service.
 *
 * Flow:
 *   1. ERP calls triggerVerification()  →  FastAPI starts async pipeline
 *   2. FastAPI completes pipeline       →  calls POST /api/applications/{id}/verification-result
 *   3. ERP calls applyVerificationResult() to persist decision
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VerificationService {

    private final ApplicationRepository applicationRepository;
    private final AiServiceClient aiServiceClient;

    /**
     * Submit an application for AI document verification.
     * Sets status to UNDER_REVIEW and calls FastAPI.
     */
    @Transactional
    public void triggerVerification(String applicationId) {
        Application app = applicationRepository.findById(applicationId)
                .orElseThrow(() -> new EntityNotFoundException("Application not found: " + applicationId));

        app.setStatus(ApplicationStatus.UNDER_REVIEW);
        applicationRepository.save(app);

        boolean accepted = aiServiceClient.triggerVerification(applicationId);
        if (!accepted) {
            log.warn("FastAPI did not accept verification trigger for {}", applicationId);
        }
    }

    /**
     * Handle the callback from FastAPI with the final verification decision.
     * Maps FastAPI decision string to VerificationDecision enum and updates ApplicationStatus.
     */
    @Transactional
    public void applyVerificationResult(String applicationId, VerificationCallbackRequest callback) {
        Application app = applicationRepository.findById(applicationId)
                .orElseThrow(() -> new EntityNotFoundException("Application not found: " + applicationId));

        VerificationDecision decision = mapDecision(callback.getDecision());

        app.setVerificationDecision(decision);
        app.setVerificationScore(callback.getOverallScore());
        app.setDecisionReason(callback.getDecisionReason());

        // Map decision to application lifecycle status
        app.setStatus(switch (decision) {
            case APPROVED       -> ApplicationStatus.COMPLETED;
            case REJECTED       -> ApplicationStatus.REJECTED;
            case MANUAL_REVIEW  -> ApplicationStatus.UNDER_REVIEW;
            default             -> ApplicationStatus.UNDER_REVIEW;
        });

        applicationRepository.save(app);
        log.info("Application {} verification result applied: {} (score={})",
                applicationId, decision, callback.getOverallScore());
    }

    private VerificationDecision mapDecision(String raw) {
        if (raw == null) return VerificationDecision.PENDING;
        return switch (raw.toUpperCase()) {
            case "APPROVED"      -> VerificationDecision.APPROVED;
            case "REJECTED"      -> VerificationDecision.REJECTED;
            case "MANUAL_REVIEW" -> VerificationDecision.MANUAL_REVIEW;
            default -> {
                log.warn("Unknown verification decision from FastAPI: {}", raw);
                yield VerificationDecision.MANUAL_REVIEW;
            }
        };
    }
}
