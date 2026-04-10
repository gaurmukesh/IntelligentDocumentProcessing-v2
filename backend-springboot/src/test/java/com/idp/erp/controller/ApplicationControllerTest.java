package com.idp.erp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.idp.erp.dto.ApplicationRequest;
import com.idp.erp.dto.ApplicationResponse;
import com.idp.erp.dto.StatusUpdateRequest;
import com.idp.erp.dto.VerificationCallbackRequest;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import com.idp.erp.service.ApplicationService;
import com.idp.erp.service.VerificationService;
import jakarta.persistence.EntityNotFoundException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ApplicationController.class)
@DisplayName("ApplicationController Integration Tests")
class ApplicationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ApplicationService applicationService;

    @MockBean
    private VerificationService verificationService;

    private ApplicationResponse buildResponse(String id, ApplicationStatus status) {
        return ApplicationResponse.builder()
                .id(id)
                .studentId("student-001")
                .studentName("Rahul Sharma")
                .courseApplied("B.Tech Computer Science")
                .status(status)
                .verificationDecision(VerificationDecision.PENDING)
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();
    }

    // ── POST /api/applications ────────────────────────────────────

    @Test
    @DisplayName("POST /api/applications returns 201 with valid request")
    void create_validRequest_returns201() throws Exception {
        ApplicationRequest request = new ApplicationRequest();
        request.setStudentId("student-001");

        when(applicationService.create(any())).thenReturn(buildResponse("app-001", ApplicationStatus.DRAFT));

        mockMvc.perform(post("/api/applications")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value("app-001"))
                .andExpect(jsonPath("$.status").value("DRAFT"))
                .andExpect(jsonPath("$.studentId").value("student-001"));
    }

    @Test
    @DisplayName("POST /api/applications returns 422 when studentId is missing")
    void create_missingStudentId_returns422() throws Exception {
        ApplicationRequest request = new ApplicationRequest();
        // studentId intentionally missing

        mockMvc.perform(post("/api/applications")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /api/applications returns 404 when student not found")
    void create_studentNotFound_returns404() throws Exception {
        ApplicationRequest request = new ApplicationRequest();
        request.setStudentId("unknown-student");

        when(applicationService.create(any()))
                .thenThrow(new EntityNotFoundException("Student not found: unknown-student"));

        mockMvc.perform(post("/api/applications")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNotFound());
    }

    // ── GET /api/applications/{id} ────────────────────────────────

    @Test
    @DisplayName("GET /api/applications/{id} returns 200 for existing application")
    void getById_existingId_returns200() throws Exception {
        when(applicationService.getById("app-001")).thenReturn(buildResponse("app-001", ApplicationStatus.DRAFT));

        mockMvc.perform(get("/api/applications/app-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("app-001"))
                .andExpect(jsonPath("$.status").value("DRAFT"));
    }

    @Test
    @DisplayName("GET /api/applications/{id} returns 404 for unknown application")
    void getById_unknownId_returns404() throws Exception {
        when(applicationService.getById("unknown"))
                .thenThrow(new EntityNotFoundException("Application not found: unknown"));

        mockMvc.perform(get("/api/applications/unknown"))
                .andExpect(status().isNotFound());
    }

    // ── GET /api/applications ─────────────────────────────────────

    @Test
    @DisplayName("GET /api/applications returns all applications")
    void getAll_returnsAllApplications() throws Exception {
        when(applicationService.getAll(null)).thenReturn(List.of(
                buildResponse("app-001", ApplicationStatus.DRAFT),
                buildResponse("app-002", ApplicationStatus.SUBMITTED)
        ));

        mockMvc.perform(get("/api/applications"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2));
    }

    @Test
    @DisplayName("GET /api/applications?status=SUBMITTED filters by status")
    void getAll_withStatusFilter_returnsFiltered() throws Exception {
        when(applicationService.getAll(ApplicationStatus.SUBMITTED))
                .thenReturn(List.of(buildResponse("app-002", ApplicationStatus.SUBMITTED)));

        mockMvc.perform(get("/api/applications").param("status", "SUBMITTED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].status").value("SUBMITTED"));
    }

    // ── PUT /api/applications/{id}/status ─────────────────────────

    @Test
    @DisplayName("PUT /api/applications/{id}/status updates status to COMPLETED")
    void updateStatus_validRequest_returns200() throws Exception {
        StatusUpdateRequest updateRequest = new StatusUpdateRequest();
        updateRequest.setStatus(ApplicationStatus.COMPLETED);
        updateRequest.setVerificationDecision(VerificationDecision.APPROVED);
        updateRequest.setVerificationScore(0.92);
        updateRequest.setDecisionReason("All checks passed");

        ApplicationResponse updated = ApplicationResponse.builder()
                .id("app-001")
                .studentId("student-001")
                .studentName("Rahul Sharma")
                .courseApplied("B.Tech")
                .status(ApplicationStatus.COMPLETED)
                .verificationDecision(VerificationDecision.APPROVED)
                .verificationScore(0.92)
                .decisionReason("All checks passed")
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();

        when(applicationService.updateStatus(eq("app-001"), any())).thenReturn(updated);

        mockMvc.perform(put("/api/applications/app-001/status")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(updateRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.verificationDecision").value("APPROVED"))
                .andExpect(jsonPath("$.verificationScore").value(0.92));
    }

    @Test
    @DisplayName("PUT /api/applications/{id}/status returns 404 for unknown application")
    void updateStatus_unknownId_returns404() throws Exception {
        StatusUpdateRequest updateRequest = new StatusUpdateRequest();
        updateRequest.setStatus(ApplicationStatus.COMPLETED);

        when(applicationService.updateStatus(eq("unknown"), any()))
                .thenThrow(new EntityNotFoundException("Application not found: unknown"));

        mockMvc.perform(put("/api/applications/unknown/status")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(updateRequest)))
                .andExpect(status().isNotFound());
    }

    // ── GET /api/applications/student/{studentId} ─────────────────

    @Test
    @DisplayName("GET /api/applications/student/{studentId} returns student applications")
    void getByStudent_returnsApplications() throws Exception {
        when(applicationService.getByStudent("student-001"))
                .thenReturn(List.of(buildResponse("app-001", ApplicationStatus.DRAFT)));

        mockMvc.perform(get("/api/applications/student/student-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].studentId").value("student-001"));
    }

    // ── POST /api/applications/{id}/trigger-verification ─────────

    @Test
    @DisplayName("POST /api/applications/{id}/trigger-verification returns 202")
    void triggerVerification_returns202() throws Exception {
        doNothing().when(verificationService).triggerVerification("app-001");

        mockMvc.perform(post("/api/applications/app-001/trigger-verification"))
                .andExpect(status().isAccepted());

        verify(verificationService).triggerVerification("app-001");
    }

    @Test
    @DisplayName("POST /api/applications/{id}/trigger-verification returns 404 when not found")
    void triggerVerification_notFound_returns404() throws Exception {
        doThrow(new EntityNotFoundException("Application not found: missing"))
                .when(verificationService).triggerVerification("missing");

        mockMvc.perform(post("/api/applications/missing/trigger-verification"))
                .andExpect(status().isNotFound());
    }

    // ── POST /api/applications/{id}/verification-result ──────────

    @Test
    @DisplayName("POST /api/applications/{id}/verification-result returns 200 on approved")
    void verificationResult_approved_returns200() throws Exception {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("APPROVED");
        req.setOverallScore(0.92);
        req.setDecisionReason("All checks passed");

        doNothing().when(verificationService).applyVerificationResult(eq("app-001"), any());

        mockMvc.perform(post("/api/applications/app-001/verification-result")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk());

        verify(verificationService).applyVerificationResult(eq("app-001"), any());
    }

    @Test
    @DisplayName("POST /api/applications/{id}/verification-result returns 400 when decision missing")
    void verificationResult_missingDecision_returns400() throws Exception {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        // decision intentionally missing

        mockMvc.perform(post("/api/applications/app-001/verification-result")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /api/applications/{id}/verification-result returns 404 when app not found")
    void verificationResult_notFound_returns404() throws Exception {
        VerificationCallbackRequest req = new VerificationCallbackRequest();
        req.setDecision("APPROVED");

        doThrow(new EntityNotFoundException("Application not found: missing"))
                .when(verificationService).applyVerificationResult(eq("missing"), any());

        mockMvc.perform(post("/api/applications/missing/verification-result")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isNotFound());
    }
}
