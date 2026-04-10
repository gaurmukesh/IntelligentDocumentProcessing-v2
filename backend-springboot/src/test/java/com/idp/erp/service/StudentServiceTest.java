package com.idp.erp.service;

import com.idp.erp.dto.StudentRequest;
import com.idp.erp.dto.StudentResponse;
import com.idp.erp.entity.Student;
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
@DisplayName("StudentService Unit Tests")
class StudentServiceTest {

    @Mock
    private StudentRepository studentRepository;

    @InjectMocks
    private StudentService studentService;

    private StudentRequest validRequest;
    private Student savedStudent;

    @BeforeEach
    void setUp() {
        validRequest = new StudentRequest();
        validRequest.setFullName("Rahul Sharma");
        validRequest.setEmail("rahul@example.com");
        validRequest.setPhone("9876543210");
        validRequest.setDateOfBirth(LocalDate.of(2003, 8, 15));
        validRequest.setCourseApplied("B.Tech Computer Science");

        savedStudent = Student.builder()
                .id("student-001")
                .fullName("Rahul Sharma")
                .email("rahul@example.com")
                .phone("9876543210")
                .dateOfBirth(LocalDate.of(2003, 8, 15))
                .courseApplied("B.Tech Computer Science")
                .build();
    }

    // ── register() ────────────────────────────────────────────────

    @Test
    @DisplayName("Register student with valid data returns response")
    void register_validData_returnsStudentResponse() {
        when(studentRepository.existsByEmail(validRequest.getEmail())).thenReturn(false);
        when(studentRepository.save(any(Student.class))).thenReturn(savedStudent);

        StudentResponse response = studentService.register(validRequest);

        assertThat(response).isNotNull();
        assertThat(response.getFullName()).isEqualTo("Rahul Sharma");
        assertThat(response.getEmail()).isEqualTo("rahul@example.com");
        assertThat(response.getId()).isEqualTo("student-001");
    }

    @Test
    @DisplayName("Register with duplicate email throws IllegalArgumentException")
    void register_duplicateEmail_throwsException() {
        when(studentRepository.existsByEmail(validRequest.getEmail())).thenReturn(true);

        assertThatThrownBy(() -> studentService.register(validRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("already exists");

        verify(studentRepository, never()).save(any());
    }

    @Test
    @DisplayName("Register saves student to repository")
    void register_callsSave_once() {
        when(studentRepository.existsByEmail(any())).thenReturn(false);
        when(studentRepository.save(any(Student.class))).thenReturn(savedStudent);

        studentService.register(validRequest);

        verify(studentRepository, times(1)).save(any(Student.class));
    }

    // ── getById() ─────────────────────────────────────────────────

    @Test
    @DisplayName("getById with existing ID returns student response")
    void getById_existingId_returnsStudentResponse() {
        when(studentRepository.findById("student-001")).thenReturn(Optional.of(savedStudent));

        StudentResponse response = studentService.getById("student-001");

        assertThat(response.getId()).isEqualTo("student-001");
        assertThat(response.getFullName()).isEqualTo("Rahul Sharma");
    }

    @Test
    @DisplayName("getById with unknown ID throws EntityNotFoundException")
    void getById_unknownId_throwsEntityNotFoundException() {
        when(studentRepository.findById("unknown-id")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> studentService.getById("unknown-id"))
                .isInstanceOf(EntityNotFoundException.class)
                .hasMessageContaining("Student not found");
    }

    // ── getAll() ──────────────────────────────────────────────────

    @Test
    @DisplayName("getAll returns list of all students")
    void getAll_returnsAllStudents() {
        Student student2 = Student.builder()
                .id("student-002")
                .fullName("Priya Singh")
                .email("priya@example.com")
                .phone("9123456789")
                .dateOfBirth(LocalDate.of(2002, 5, 20))
                .courseApplied("B.Sc Physics")
                .build();

        when(studentRepository.findAll()).thenReturn(List.of(savedStudent, student2));

        List<StudentResponse> responses = studentService.getAll();

        assertThat(responses).hasSize(2);
        assertThat(responses).extracting(StudentResponse::getEmail)
                .containsExactlyInAnyOrder("rahul@example.com", "priya@example.com");
    }

    @Test
    @DisplayName("getAll returns empty list when no students exist")
    void getAll_noStudents_returnsEmptyList() {
        when(studentRepository.findAll()).thenReturn(List.of());

        List<StudentResponse> responses = studentService.getAll();

        assertThat(responses).isEmpty();
    }
}
