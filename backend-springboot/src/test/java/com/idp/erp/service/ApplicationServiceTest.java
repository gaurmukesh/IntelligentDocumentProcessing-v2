package com.idp.erp.service;

import com.idp.erp.dto.ApplicationRequest;
import com.idp.erp.dto.ApplicationResponse;
import com.idp.erp.dto.StatusUpdateRequest;
import com.idp.erp.entity.Application;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Application.VerificationDecision;
import com.idp.erp.entity.Student;
import com.idp.erp.repository.ApplicationRepository;
import com.idp.erp.repository.StudentRepository;
import jakarta.persistence.EntityNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("ApplicationService Unit Tests")
class ApplicationServiceTest {

    @Mock
    private ApplicationRepository applicationRepository;

    @Mock
    private StudentRepository studentRepository;

    @InjectMocks
    private ApplicationService applicationService;

    private Student student;
    private Application application;

    @BeforeEach
    void setUp() {
        student = Student.builder()
                .id("student-001")
                .fullName("Rahul Sharma")
                .email("rahul@example.com")
                .phone("9876543210")
                .dateOfBirth(LocalDate.of(2003, 8, 15))
                .courseApplied("B.Tech Computer Science")
                .build();

        application = Application.builder()
                .id("app-001")
                .student(student)
                .status(ApplicationStatus.DRAFT)
                .verificationDecision(VerificationDecision.PENDING)
                .build();
    }

    // ── create() ──────────────────────────────────────────────────

    @Test
    @DisplayName("Create application with valid student ID returns response")
    void create_validStudentId_returnsApplicationResponse() {
        ApplicationRequest request = new ApplicationRequest();
        request.setStudentId("student-001");

        when(studentRepository.findById("student-001")).thenReturn(Optional.of(student));
        when(applicationRepository.save(any(Application.class))).thenReturn(application);

        ApplicationResponse response = applicationService.create(request);

        assertThat(response).isNotNull();
        assertThat(response.getId()).isEqualTo("app-001");
        assertThat(response.getStudentId()).isEqualTo("student-001");
        assertThat(response.getStatus()).isEqualTo(ApplicationStatus.DRAFT);
        assertThat(response.getVerificationDecision()).isEqualTo(VerificationDecision.PENDING);
    }

    @Test
    @DisplayName("Create application with unknown student ID throws EntityNotFoundException")
    void create_unknownStudentId_throwsEntityNotFoundException() {
        ApplicationRequest request = new ApplicationRequest();
        request.setStudentId("unknown-id");

        when(studentRepository.findById("unknown-id")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> applicationService.create(request))
                .isInstanceOf(EntityNotFoundException.class)
                .hasMessageContaining("Student not found");

        verify(applicationRepository, never()).save(any());
    }

    @Test
    @DisplayName("Create sets initial status to DRAFT")
    void create_setsInitialStatusToDraft() {
        ApplicationRequest request = new ApplicationRequest();
        request.setStudentId("student-001");

        when(studentRepository.findById("student-001")).thenReturn(Optional.of(student));
        when(applicationRepository.save(any(Application.class))).thenAnswer(inv -> {
            Application app = inv.getArgument(0);
            app.setId("app-new");
            return app;
        });

        ApplicationResponse response = applicationService.create(request);

        assertThat(response.getStatus()).isEqualTo(ApplicationStatus.DRAFT);
    }

    // ── getById() ─────────────────────────────────────────────────

    @Test
    @DisplayName("getById with existing ID returns application response")
    void getById_existingId_returnsApplicationResponse() {
        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));

        ApplicationResponse response = applicationService.getById("app-001");

        assertThat(response.getId()).isEqualTo("app-001");
        assertThat(response.getStudentName()).isEqualTo("Rahul Sharma");
    }

    @Test
    @DisplayName("getById with unknown ID throws EntityNotFoundException")
    void getById_unknownId_throwsEntityNotFoundException() {
        when(applicationRepository.findById("unknown")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> applicationService.getById("unknown"))
                .isInstanceOf(EntityNotFoundException.class)
                .hasMessageContaining("Application not found");
    }

    // ── getAll() ──────────────────────────────────────────────────

    @Test
    @DisplayName("getAll without filter returns all applications")
    void getAll_noFilter_returnsAll() {
        when(applicationRepository.findAll()).thenReturn(List.of(application));

        List<ApplicationResponse> responses = applicationService.getAll(null);

        assertThat(responses).hasSize(1);
    }

    @Test
    @DisplayName("getAll with status filter returns filtered applications")
    void getAll_withStatusFilter_returnsFiltered() {
        when(applicationRepository.findByStatus(ApplicationStatus.DRAFT))
                .thenReturn(List.of(application));

        List<ApplicationResponse> responses = applicationService.getAll(ApplicationStatus.DRAFT);

        assertThat(responses).hasSize(1);
        assertThat(responses.get(0).getStatus()).isEqualTo(ApplicationStatus.DRAFT);
    }

    @Test
    @DisplayName("getAll returns empty list when no applications exist")
    void getAll_noApplications_returnsEmptyList() {
        when(applicationRepository.findAll()).thenReturn(List.of());

        List<ApplicationResponse> responses = applicationService.getAll(null);

        assertThat(responses).isEmpty();
    }

    // ── updateStatus() ────────────────────────────────────────────

    @Test
    @DisplayName("updateStatus updates application status correctly")
    void updateStatus_validRequest_updatesStatus() {
        StatusUpdateRequest updateRequest = new StatusUpdateRequest();
        updateRequest.setStatus(ApplicationStatus.COMPLETED);
        updateRequest.setVerificationDecision(VerificationDecision.APPROVED);
        updateRequest.setVerificationScore(0.92);
        updateRequest.setDecisionReason("All checks passed");

        when(applicationRepository.findById("app-001")).thenReturn(Optional.of(application));
        when(applicationRepository.save(any(Application.class))).thenAnswer(inv -> inv.getArgument(0));

        ApplicationResponse response = applicationService.updateStatus("app-001", updateRequest);

        assertThat(response.getStatus()).isEqualTo(ApplicationStatus.COMPLETED);
        assertThat(response.getVerificationDecision()).isEqualTo(VerificationDecision.APPROVED);
        assertThat(response.getVerificationScore()).isEqualTo(0.92);
        assertThat(response.getDecisionReason()).isEqualTo("All checks passed");
    }

    @Test
    @DisplayName("updateStatus with unknown ID throws EntityNotFoundException")
    void updateStatus_unknownId_throwsEntityNotFoundException() {
        StatusUpdateRequest updateRequest = new StatusUpdateRequest();
        updateRequest.setStatus(ApplicationStatus.COMPLETED);

        when(applicationRepository.findById("unknown")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> applicationService.updateStatus("unknown", updateRequest))
                .isInstanceOf(EntityNotFoundException.class)
                .hasMessageContaining("Application not found");
    }

    // ── getByStudent() ────────────────────────────────────────────

    @Test
    @DisplayName("getByStudent returns applications for given student")
    void getByStudent_returnsApplicationsForStudent() {
        when(applicationRepository.findByStudentId("student-001"))
                .thenReturn(List.of(application));

        List<ApplicationResponse> responses = applicationService.getByStudent("student-001");

        assertThat(responses).hasSize(1);
        assertThat(responses.get(0).getStudentId()).isEqualTo("student-001");
    }
}
