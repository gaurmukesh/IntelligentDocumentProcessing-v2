package com.idp.erp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.idp.erp.dto.StudentRequest;
import com.idp.erp.dto.StudentResponse;
import com.idp.erp.service.StudentService;
import jakarta.persistence.EntityNotFoundException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(StudentController.class)
@DisplayName("StudentController Integration Tests")
class StudentControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private StudentService studentService;

    private StudentResponse buildResponse(String id, String name, String email) {
        return StudentResponse.builder()
                .id(id)
                .fullName(name)
                .email(email)
                .phone("9876543210")
                .dateOfBirth(LocalDate.of(2003, 8, 15))
                .courseApplied("B.Tech")
                .createdAt(LocalDateTime.now())
                .build();
    }

    // ── POST /api/students ────────────────────────────────────────

    @Test
    @DisplayName("POST /api/students returns 201 with valid request")
    void registerStudent_validRequest_returns201() throws Exception {
        StudentRequest request = new StudentRequest();
        request.setFullName("Rahul Sharma");
        request.setEmail("rahul@example.com");
        request.setPhone("9876543210");
        request.setDateOfBirth(LocalDate.of(2003, 8, 15));
        request.setCourseApplied("B.Tech Computer Science");

        when(studentService.register(any())).thenReturn(buildResponse("s-001", "Rahul Sharma", "rahul@example.com"));

        mockMvc.perform(post("/api/students")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value("s-001"))
                .andExpect(jsonPath("$.fullName").value("Rahul Sharma"))
                .andExpect(jsonPath("$.email").value("rahul@example.com"));
    }

    @Test
    @DisplayName("POST /api/students returns 400 when email is missing")
    void registerStudent_missingEmail_returns422() throws Exception {
        StudentRequest request = new StudentRequest();
        request.setFullName("Rahul Sharma");
        // email intentionally missing
        request.setPhone("9876543210");
        request.setDateOfBirth(LocalDate.of(2003, 8, 15));
        request.setCourseApplied("B.Tech");

        mockMvc.perform(post("/api/students")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /api/students returns 400 when email is invalid")
    void registerStudent_invalidEmail_returns422() throws Exception {
        StudentRequest request = new StudentRequest();
        request.setFullName("Rahul Sharma");
        request.setEmail("not-an-email");
        request.setPhone("9876543210");
        request.setDateOfBirth(LocalDate.of(2003, 8, 15));
        request.setCourseApplied("B.Tech");

        mockMvc.perform(post("/api/students")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /api/students returns 400 when duplicate email")
    void registerStudent_duplicateEmail_returns400() throws Exception {
        StudentRequest request = new StudentRequest();
        request.setFullName("Rahul Sharma");
        request.setEmail("rahul@example.com");
        request.setPhone("9876543210");
        request.setDateOfBirth(LocalDate.of(2003, 8, 15));
        request.setCourseApplied("B.Tech");

        when(studentService.register(any()))
                .thenThrow(new IllegalArgumentException("Student with email rahul@example.com already exists"));

        mockMvc.perform(post("/api/students")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Student with email rahul@example.com already exists"));
    }

    // ── GET /api/students/{id} ────────────────────────────────────

    @Test
    @DisplayName("GET /api/students/{id} returns 200 for existing student")
    void getById_existingId_returns200() throws Exception {
        when(studentService.getById("s-001")).thenReturn(buildResponse("s-001", "Rahul Sharma", "rahul@example.com"));

        mockMvc.perform(get("/api/students/s-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("s-001"))
                .andExpect(jsonPath("$.fullName").value("Rahul Sharma"));
    }

    @Test
    @DisplayName("GET /api/students/{id} returns 404 for unknown student")
    void getById_unknownId_returns404() throws Exception {
        when(studentService.getById("unknown")).thenThrow(new EntityNotFoundException("Student not found: unknown"));

        mockMvc.perform(get("/api/students/unknown"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("Student not found: unknown"));
    }

    // ── GET /api/students ─────────────────────────────────────────

    @Test
    @DisplayName("GET /api/students returns 200 with list of students")
    void getAll_returnsStudentList() throws Exception {
        when(studentService.getAll()).thenReturn(List.of(
                buildResponse("s-001", "Rahul Sharma", "rahul@example.com"),
                buildResponse("s-002", "Priya Singh",  "priya@example.com")
        ));

        mockMvc.perform(get("/api/students"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].fullName").value("Rahul Sharma"))
                .andExpect(jsonPath("$[1].fullName").value("Priya Singh"));
    }

    @Test
    @DisplayName("GET /api/students returns empty list when no students")
    void getAll_noStudents_returnsEmptyList() throws Exception {
        when(studentService.getAll()).thenReturn(List.of());

        mockMvc.perform(get("/api/students"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
    }
}
