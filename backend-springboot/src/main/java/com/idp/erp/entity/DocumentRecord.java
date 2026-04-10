package com.idp.erp.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "document_records")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class DocumentRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "application_id", nullable = false)
    private Application application;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DocumentType docType;

    @Column(nullable = false)
    private String fileName;

    @Column(nullable = false)
    private String filePath;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DocumentStatus status;

    @CreationTimestamp
    private LocalDateTime uploadedAt;

    public enum DocumentType {
        MARKSHEET_10TH, MARKSHEET_12TH, AADHAR
    }

    public enum DocumentStatus {
        PENDING, PROCESSING, VERIFIED, FAILED
    }
}
