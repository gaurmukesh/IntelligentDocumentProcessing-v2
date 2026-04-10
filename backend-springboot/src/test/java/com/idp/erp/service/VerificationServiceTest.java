package com.idp.erp.service;

import com.idp.erp.client.AiServiceClient;
import com.idp.erp.dto.VerificationCallbackRequest;
import com.idp.erp.entity.Application;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import com.idp.erp.entity.Student;
import com.idp.erp.repository.ApplicationRepository;
import jakarta.persistence.EntityNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class VerificationServiceTest {

    @Mock private ApplicationRepository applicationRepository;
    @Mock private AiServiceClient aiServiceClient;

    @InjectMocks
    private VerificationService verificationService;

    private Application application;

    @BeforeEach
    void setUp() {
        Student student = Student.builder()
                .id("s-001").fullName("Rahul Sharma").email("rahul@test.com")
                .courseApplied("B.Tech").build();

        application = Application.builder()
                .id("app-001").student(student)
                .status(ApplicationStatus.SUBMITTED)
                .verificationDecision(VerificationDecision.PENDING)
                .build();
    }

    // ── triggerVerification ───────────────────────────────────────

    @Test
    void triggerVerification_setsStatusToUnderReview() {
        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);
        when(aiServiceClient.triggerVerification("app-001")).thenReturn(true);

        verificationService.triggerVerification("app-001");

        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.UNDER_REVIEW);
        verify(applicationRepository).save(application);
        verify(aiServiceClient).triggerVerification("app-001");
    }

    @Test
    void triggerVerification_throwsWhenApplicationNotFound() {
        when(applicationRepository.findById("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> verificationService.triggerVerification("missing"))
                .isInstanceOf(EntityNotFoundException.class)
                .hasMessageContaining("missing");
    }

    @Test
    void triggerVerification_continuesWhenFastApiRejectsTrigger() {
        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);
        when(aiServiceClient.triggerVerification("app-001")).thenReturn(false);

        // Should not throw — FastAPI rejection is logged but not fatal
        verificationService.triggerVerification("app-001");

        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.UNDER_REVIEW);
    }

    // ── applyVerificationResult ───────────────────────────────────

    @Test
    void applyVerificationResult_approved_setsCompletedStatus() {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("APPROVED");
        req.setOverallScore(0.92);
        req.setDecisionReason("All checks passed");

        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);

        verificationService.applyVerificationResult("app-001", req);

        assertThat(application.getVerificationDecision()).isEqualTo(VerificationDecision.APPROVED);
        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.COMPLETED);
        assertThat(application.getVerificationScore()).isEqualTo(0.92);
        assertThat(application.getDecisionReason()).isEqualTo("All checks passed");
    }

    @Test
    void applyVerificationResult_rejected_setsRejectedStatus() {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("REJECTED");
        req.setOverallScore(0.35);
        req.setDecisionReason("DOB mismatch");

        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);

        verificationService.applyVerificationResult("app-001", req);

        assertThat(application.getVerificationDecision()).isEqualTo(VerificationDecision.REJECTED);
        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.REJECTED);
    }

    @Test
    void applyVerificationResult_manualReview_setsUnderReviewStatus() {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("MANUAL_REVIEW");
        req.setOverallScore(0.68);
        req.setDecisionReason("Name mismatch requires human check");

        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);

        verificationService.applyVerificationResult("app-001", req);

        assertThat(application.getVerificationDecision()).isEqualTo(VerificationDecision.MANUAL_REVIEW);
        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.UNDER_REVIEW);
    }

    @Test
    void applyVerificationResult_unknownDecision_defaultsToManualReview() {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("UNKNOWN_VALUE");
        req.setOverallScore(0.5);
        req.setDecisionReason("Unexpected");

        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any())).thenReturn(application);

        verificationService.applyVerificationResult("app-001", req);

        assertThat(application.getVerificationDecision()).isEqualTo(VerificationDecision.MANUAL_REVIEW);
        assertThat(application.getStatus()).isEqualTo(ApplicationStatus.UNDER_REVIEW);
    }

    @Test
    void applyVerificationResult_throwsWhenApplicationNotFound() {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("APPROVED");

        when(applicationRepository.findById("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> verificationService.applyVerificationResult("missing", req))
                .isInstanceOf(EntityNotFoundException.class);
    }
}
