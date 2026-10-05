"""
Synthetic Spring Boot Project Generator for Large-Scale Integration & Performance Tests.
Generates ~90 types, ~200 relationships, 30 endpoints, 14 entities, 14 repositories,
auth components, strategy pattern with @Component, and Java record DTOs.
"""

import os
import io
import zipfile
import tempfile
from typing import Dict, Tuple

ENTITIES = [
    ("User", "users", [("id", "Long", True), ("email", "String", False), ("username", "String", False), ("password", "String", False)]),
    ("Order", "orders", [("id", "Long", True), ("orderNumber", "String", False), ("totalAmount", "Double", False), ("status", "String", False)]),
    ("Product", "products", [("id", "Long", True), ("name", "String", False), ("price", "Double", False), ("sku", "String", False)]),
    ("Customer", "customers", [("id", "Long", True), ("firstName", "String", False), ("lastName", "String", False), ("phone", "String", False)]),
    ("Invoice", "invoices", [("id", "Long", True), ("invoiceCode", "String", False), ("amount", "Double", False), ("dueDate", "String", False)]),
    ("Payment", "payments", [("id", "Long", True), ("transactionId", "String", False), ("amount", "Double", False), ("provider", "String", False)]),
    ("Shipment", "shipments", [("id", "Long", True), ("trackingNumber", "String", False), ("carrier", "String", False), ("status", "String", False)]),
    ("Category", "categories", [("id", "Long", True), ("title", "String", False), ("slug", "String", False)]),
    ("Review", "reviews", [("id", "Long", True), ("rating", "Integer", False), ("comment", "String", False)]),
    ("Coupon", "coupons", [("id", "Long", True), ("code", "String", False), ("discountPercent", "Double", False)]),
    ("Inventory", "inventories", [("id", "Long", True), ("stockQuantity", "Integer", False), ("warehouseLocation", "String", False)]),
    ("Address", "addresses", [("id", "Long", True), ("street", "String", False), ("city", "String", False), ("zipCode", "String", False)]),
    ("AuditLog", "audit_logs", [("id", "Long", True), ("action", "String", False), ("performedBy", "String", False), ("timestamp", "String", False)]),
    ("Notification", "notifications", [("id", "Long", True), ("recipient", "String", False), ("message", "String", False), ("isRead", "Boolean", False)]),
]

RECORDS_DTOS = [
    ("LoginRequest", "package com.example.app.dto;\n\npublic record LoginRequest(String username, String password) {}"),
    ("RegisterRequest", "package com.example.app.dto;\n\npublic record RegisterRequest(String username, String email, String password) {}"),
    ("AuthResponse", "package com.example.app.dto;\n\npublic record AuthResponse(String token, String type, String username) {}"),
    ("UserDTO", "package com.example.app.dto;\n\npublic record UserDTO(Long id, String email, String username) {}"),
    ("UserCreateRequest", "package com.example.app.dto;\n\npublic record UserCreateRequest(String email, String username, String password) {}"),
    ("OrderDTO", "package com.example.app.dto;\n\npublic record OrderDTO(Long id, String orderNumber, Double totalAmount, String status) {}"),
    ("OrderCreateRequest", "package com.example.app.dto;\n\npublic record OrderCreateRequest(Long customerId, Double totalAmount) {}"),
    ("ProductDTO", "package com.example.app.dto;\n\npublic record ProductDTO(Long id, String name, Double price, String sku) {}"),
    ("ProductCreateRequest", "package com.example.app.dto;\n\npublic record ProductCreateRequest(String name, Double price, String sku) {}"),
    ("CustomerDTO", "package com.example.app.dto;\n\npublic record CustomerDTO(Long id, String firstName, String lastName, String phone) {}"),
    ("InvoiceDTO", "package com.example.app.dto;\n\npublic record InvoiceDTO(Long id, String invoiceCode, Double amount, String dueDate) {}"),
    ("PaymentDTO", "package com.example.app.dto;\n\npublic record PaymentDTO(Long id, String transactionId, Double amount, String provider) {}"),
    ("PaymentRequest", "package com.example.app.dto;\n\npublic record PaymentRequest(Long orderId, Double amount, String paymentMethod) {}"),
    ("ShipmentDTO", "package com.example.app.dto;\n\npublic record ShipmentDTO(Long id, String trackingNumber, String carrier, String status) {}"),
    ("CategoryDTO", "package com.example.app.dto;\n\npublic record CategoryDTO(Long id, String title, String slug) {}"),
    ("ReviewDTO", "package com.example.app.dto;\n\npublic record ReviewDTO(Long id, Integer rating, String comment) {}"),
    ("CouponDTO", "package com.example.app.dto;\n\npublic record CouponDTO(Long id, String code, Double discountPercent) {}"),
    ("NotificationDTO", "package com.example.app.dto;\n\npublic record NotificationDTO(Long id, String recipient, String message, Boolean isRead) {}"),
]


def generate_large_project_files() -> Dict[str, str]:
    """Generates all source code files for the ~90-type synthetic Spring Boot project."""
    files: Dict[str, str] = {}

    # 1. pom.xml & application.properties
    files["pom.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>large-enterprise-app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-api</artifactId>
            <version>0.11.5</version>
        </dependency>
    </dependencies>
</project>
"""

    files["src/main/resources/application.properties"] = """# Database Configuration
spring.datasource.url=jdbc:postgresql://localhost:5432/enterprise_db
spring.datasource.username=postgres
spring.datasource.password=secret
spring.jpa.hibernate.ddl-auto=update
jwt.secret=9a6747f6f12c3f098c4b1234567890abcdef
"""

    # 2. Main Application Entry Point
    files["src/main/java/com/example/app/EnterpriseApplication.java"] = """package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class EnterpriseApplication {
    public static void main(String[] args) {
        SpringApplication.run(EnterpriseApplication.class, args);
    }
}
"""

    # 3. Entities (14)
    for name, tbl, flds in ENTITIES:
        field_decls = []
        for fname, ftype, is_id in flds:
            if is_id:
                field_decls.append(f"    @Id\n    @GeneratedValue(strategy = GenerationType.IDENTITY)\n    private {ftype} {fname};")
            else:
                field_decls.append(f"    private {ftype} {fname};")
        fields_str = "\n\n".join(field_decls)

        files[f"src/main/java/com/example/app/entity/{name}.java"] = f"""package com.example.app.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "{tbl}")
public class {name} {{
{fields_str}

    public {name}() {{}}
}}
"""

    # 4. Repositories (14)
    for name, _, _ in ENTITIES:
        files[f"src/main/java/com/example/app/repository/{name}Repository.java"] = f"""package com.example.app.repository;

import com.example.app.entity.{name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;
import java.util.List;

@Repository
public interface {name}Repository extends JpaRepository<{name}, Long> {{
    Optional<{name}> findById(Long id);
    List<{name}> findAll();
}}
"""

    # 5. DTO Records (18)
    for name, code in RECORDS_DTOS:
        files[f"src/main/java/com/example/app/dto/{name}.java"] = code

    # 6. Strategy Pattern Interface & @Component Implementations (4 types)
    files["src/main/java/com/example/app/strategy/PaymentStrategy.java"] = """package com.example.app.strategy;

import com.example.app.dto.PaymentRequest;
import com.example.app.dto.PaymentDTO;

public interface PaymentStrategy {
    PaymentDTO processPayment(PaymentRequest request);
    String getProviderName();
}
"""
    files["src/main/java/com/example/app/strategy/CreditCardPaymentStrategy.java"] = """package com.example.app.strategy;

import org.springframework.stereotype.Component;
import com.example.app.dto.PaymentRequest;
import com.example.app.dto.PaymentDTO;

@Component
public class CreditCardPaymentStrategy implements PaymentStrategy {
    @Override
    public PaymentDTO processPayment(PaymentRequest request) {
        return new PaymentDTO(1L, "CC-123", request.amount(), "CREDIT_CARD");
    }

    @Override
    public String getProviderName() {
        return "CREDIT_CARD";
    }
}
"""
    files["src/main/java/com/example/app/strategy/PaypalPaymentStrategy.java"] = """package com.example.app.strategy;

import org.springframework.stereotype.Component;
import com.example.app.dto.PaymentRequest;
import com.example.app.dto.PaymentDTO;

@Component
public class PaypalPaymentStrategy implements PaymentStrategy {
    @Override
    public PaymentDTO processPayment(PaymentRequest request) {
        return new PaymentDTO(2L, "PP-456", request.amount(), "PAYPAL");
    }

    @Override
    public String getProviderName() {
        return "PAYPAL";
    }
}
"""
    files["src/main/java/com/example/app/strategy/CryptoPaymentStrategy.java"] = """package com.example.app.strategy;

import org.springframework.stereotype.Component;
import com.example.app.dto.PaymentRequest;
import com.example.app.dto.PaymentDTO;

@Component
public class CryptoPaymentStrategy implements PaymentStrategy {
    @Override
    public PaymentDTO processPayment(PaymentRequest request) {
        return new PaymentDTO(3L, "CRYPTO-789", request.amount(), "CRYPTO");
    }

    @Override
    public String getProviderName() {
        return "CRYPTO";
    }
}
"""

    # 7. Services & Service Interfaces (14 standard + 1 auth = 30 types)
    for name, _, _ in ENTITIES:
        dto_type = f"{name}DTO"
        files[f"src/main/java/com/example/app/service/{name}Service.java"] = f"""package com.example.app.service;

import com.example.app.dto.{dto_type};
import java.util.List;
import java.util.Optional;

public interface {name}Service {{
    List<{dto_type}> getAll();
    Optional<{dto_type}> getById(Long id);
    {dto_type} save({dto_type} dto);
    void delete(Long id);
}}
"""

    # Service Implementations with cross-service & repository injections
    files["src/main/java/com/example/app/service/impl/UserServiceImpl.java"] = """package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.UserService;
import com.example.app.repository.UserRepository;
import com.example.app.repository.AuditLogRepository;
import com.example.app.entity.User;
import com.example.app.dto.UserDTO;
import java.util.List;
import java.util.Optional;

@Service
public class UserServiceImpl implements UserService {
    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;
    private final NotificationRepository notificationRepository;

    public UserServiceImpl(UserRepository userRepository, AuditLogRepository auditLogRepository, NotificationRepository notificationRepository) {
        this.userRepository = userRepository;
        this.auditLogRepository = auditLogRepository;
        this.notificationRepository = notificationRepository;
    }

    @Override
    public List<UserDTO> getAll() { return List.of(); }
    @Override
    public Optional<UserDTO> getById(Long id) { return Optional.empty(); }
    @Override
    public UserDTO save(UserDTO dto) { return dto; }
    @Override
    public void delete(Long id) {}
    public User findUserEntity(Long id) { return null; }
}
"""

    files["src/main/java/com/example/app/service/impl/OrderServiceImpl.java"] = """package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.OrderService;
import com.example.app.service.PaymentService;
import com.example.app.service.InventoryService;
import com.example.app.service.NotificationService;
import com.example.app.repository.OrderRepository;
import com.example.app.repository.UserRepository;
import com.example.app.repository.ProductRepository;
import com.example.app.repository.CustomerRepository;
import com.example.app.repository.ShipmentRepository;
import com.example.app.dto.OrderDTO;
import java.util.List;
import java.util.Optional;

@Service
public class OrderServiceImpl implements OrderService {
    private final OrderRepository orderRepository;
    private final UserRepository userRepository;
    private final ProductRepository productRepository;
    private final CustomerRepository customerRepository;
    private final ShipmentRepository shipmentRepository;
    private final PaymentService paymentService;
    private final InventoryService inventoryService;
    private final NotificationService notificationService;

    public OrderServiceImpl(OrderRepository orderRepository, UserRepository userRepository, ProductRepository productRepository, CustomerRepository customerRepository, ShipmentRepository shipmentRepository, PaymentService paymentService, InventoryService inventoryService, NotificationService notificationService) {
        this.orderRepository = orderRepository;
        this.userRepository = userRepository;
        this.productRepository = productRepository;
        this.customerRepository = customerRepository;
        this.shipmentRepository = shipmentRepository;
        this.paymentService = paymentService;
        this.inventoryService = inventoryService;
        this.notificationService = notificationService;
    }

    @Override
    public List<OrderDTO> getAll() { return List.of(); }
    @Override
    public Optional<OrderDTO> getById(Long id) { return Optional.empty(); }
    @Override
    public OrderDTO save(OrderDTO dto) { return dto; }
    @Override
    public void delete(Long id) {}
}
"""

    files["src/main/java/com/example/app/service/impl/ProductServiceImpl.java"] = """package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.ProductService;
import com.example.app.service.InventoryService;
import com.example.app.repository.ProductRepository;
import com.example.app.repository.CategoryRepository;
import com.example.app.repository.ReviewRepository;
import com.example.app.dto.ProductDTO;
import java.util.List;
import java.util.Optional;

@Service
public class ProductServiceImpl implements ProductService {
    private final ProductRepository productRepository;
    private final CategoryRepository categoryRepository;
    private final ReviewRepository reviewRepository;
    private final InventoryService inventoryService;

    public ProductServiceImpl(ProductRepository productRepository, CategoryRepository categoryRepository, ReviewRepository reviewRepository, InventoryService inventoryService) {
        this.productRepository = productRepository;
        this.categoryRepository = categoryRepository;
        this.reviewRepository = reviewRepository;
        this.inventoryService = inventoryService;
    }

    @Override
    public List<ProductDTO> getAll() { return List.of(); }
    @Override
    public Optional<ProductDTO> getById(Long id) { return Optional.empty(); }
    @Override
    public ProductDTO save(ProductDTO dto) { return dto; }
    @Override
    public void delete(Long id) {}
}
"""

    files["src/main/java/com/example/app/service/impl/PaymentServiceImpl.java"] = """package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.PaymentService;
import com.example.app.strategy.CreditCardPaymentStrategy;
import com.example.app.strategy.PaypalPaymentStrategy;
import com.example.app.strategy.CryptoPaymentStrategy;
import com.example.app.repository.PaymentRepository;
import com.example.app.repository.InvoiceRepository;
import com.example.app.repository.AuditLogRepository;
import com.example.app.dto.PaymentDTO;
import java.util.List;
import java.util.Optional;

@Service
public class PaymentServiceImpl implements PaymentService {
    private final PaymentRepository paymentRepository;
    private final InvoiceRepository invoiceRepository;
    private final AuditLogRepository auditLogRepository;
    private final CreditCardPaymentStrategy creditCardPaymentStrategy;
    private final PaypalPaymentStrategy paypalPaymentStrategy;
    private final CryptoPaymentStrategy cryptoPaymentStrategy;

    public PaymentServiceImpl(PaymentRepository paymentRepository, InvoiceRepository invoiceRepository, AuditLogRepository auditLogRepository, CreditCardPaymentStrategy creditCardPaymentStrategy, PaypalPaymentStrategy paypalPaymentStrategy, CryptoPaymentStrategy cryptoPaymentStrategy) {
        this.paymentRepository = paymentRepository;
        this.invoiceRepository = invoiceRepository;
        this.auditLogRepository = auditLogRepository;
        this.creditCardPaymentStrategy = creditCardPaymentStrategy;
        this.paypalPaymentStrategy = paypalPaymentStrategy;
        this.cryptoPaymentStrategy = cryptoPaymentStrategy;
    }

    @Override
    public List<PaymentDTO> getAll() { return List.of(); }
    @Override
    public Optional<PaymentDTO> getById(Long id) { return Optional.empty(); }
    @Override
    public PaymentDTO save(PaymentDTO dto) { return dto; }
    @Override
    public void delete(Long id) {}
}
"""

    # Remaining services
    for name, _, _ in ENTITIES:
        if name in ["User", "Order", "Product", "Payment"]:
            continue
        dto_type = f"{name}DTO"
        files[f"src/main/java/com/example/app/service/impl/{name}ServiceImpl.java"] = f"""package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.{name}Service;
import com.example.app.repository.{name}Repository;
import com.example.app.repository.AuditLogRepository;
import com.example.app.repository.NotificationRepository;
import com.example.app.repository.UserRepository;
import com.example.app.repository.ProductRepository;
import com.example.app.repository.OrderRepository;
import com.example.app.dto.{dto_type};
import java.util.List;
import java.util.Optional;

@Service
public class {name}ServiceImpl implements {name}Service {{
    private final {name}Repository {name.lower()}Repository;
    private final AuditLogRepository auditLogRepository;
    private final NotificationRepository notificationRepository;
    private final UserRepository userRepository;
    private final ProductRepository productRepository;
    private final OrderRepository orderRepository;

    public {name}ServiceImpl({name}Repository {name.lower()}Repository, AuditLogRepository auditLogRepository, NotificationRepository notificationRepository, UserRepository userRepository, ProductRepository productRepository, OrderRepository orderRepository) {{
        this.{name.lower()}Repository = {name.lower()}Repository;
        this.auditLogRepository = auditLogRepository;
        this.notificationRepository = notificationRepository;
        this.userRepository = userRepository;
        this.productRepository = productRepository;
        this.orderRepository = orderRepository;
    }}

    @Override
    public List<{dto_type}> getAll() {{ return List.of(); }}
    @Override
    public Optional<{dto_type}> getById(Long id) {{ return Optional.empty(); }}
    @Override
    public {dto_type} save({dto_type} dto) {{ return dto; }}
    @Override
    public void delete(Long id) {{}}
}}
"""

    # Auth Service
    files["src/main/java/com/example/app/service/AuthService.java"] = """package com.example.app.service;

import com.example.app.dto.LoginRequest;
import com.example.app.dto.RegisterRequest;
import com.example.app.dto.AuthResponse;

public interface AuthService {
    AuthResponse login(LoginRequest request);
    AuthResponse register(RegisterRequest request);
    AuthResponse refreshToken(String token);
    void logout(String token);
}
"""
    files["src/main/java/com/example/app/service/impl/AuthServiceImpl.java"] = """package com.example.app.service.impl;

import org.springframework.stereotype.Service;
import com.example.app.service.AuthService;
import com.example.app.service.UserService;
import com.example.app.service.NotificationService;
import com.example.app.repository.UserRepository;
import com.example.app.repository.AuditLogRepository;
import com.example.app.config.JwtTokenProvider;
import com.example.app.dto.LoginRequest;
import com.example.app.dto.RegisterRequest;
import com.example.app.dto.AuthResponse;

@Service
public class AuthServiceImpl implements AuthService {
    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;
    private final UserService userService;
    private final NotificationService notificationService;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthServiceImpl(UserRepository userRepository, AuditLogRepository auditLogRepository, UserService userService, NotificationService notificationService, JwtTokenProvider jwtTokenProvider) {
        this.userRepository = userRepository;
        this.auditLogRepository = auditLogRepository;
        this.userService = userService;
        this.notificationService = notificationService;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    public AuthResponse login(LoginRequest request) { return new AuthResponse("token123", "Bearer", request.username()); }
    @Override
    public AuthResponse register(RegisterRequest request) { return new AuthResponse("token456", "Bearer", request.username()); }
    @Override
    public AuthResponse refreshToken(String token) { return new AuthResponse("token789", "Bearer", "refreshedUser"); }
    @Override
    public void logout(String token) {}
}
"""

    # 8. Controllers (8 controllers = 30 endpoints total)
    files["src/main/java/com/example/app/controller/AuthController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.AuthService;
import com.example.app.dto.LoginRequest;
import com.example.app.dto.RegisterRequest;
import com.example.app.dto.AuthResponse;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/login")
    public AuthResponse login(@RequestBody LoginRequest request) {
        return authService.login(request);
    }

    @PostMapping("/register")
    public AuthResponse register(@RequestBody RegisterRequest request) {
        return authService.register(request);
    }

    @PostMapping("/refresh")
    public AuthResponse refresh(@RequestParam String token) {
        return authService.refreshToken(token);
    }

    @PostMapping("/logout")
    public void logout(@RequestParam String token) {
        authService.logout(token);
    }
}
"""

    files["src/main/java/com/example/app/controller/UserController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.UserService;
import com.example.app.dto.UserDTO;
import com.example.app.dto.UserCreateRequest;
import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {
    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public List<UserDTO> listUsers() {
        return userService.getAll();
    }

    @GetMapping("/{id}")
    public UserDTO getUser(@PathVariable Long id) {
        return userService.getById(id).orElse(null);
    }

    @PostMapping
    public UserDTO createUser(@RequestBody UserCreateRequest request) {
        return userService.save(new UserDTO(null, request.email(), request.username()));
    }

    @DeleteMapping("/{id}")
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }
}
"""

    files["src/main/java/com/example/app/controller/OrderController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.OrderService;
import com.example.app.service.CustomerService;
import com.example.app.service.PaymentService;
import com.example.app.dto.OrderDTO;
import com.example.app.dto.OrderCreateRequest;
import java.util.List;

@RestController
@RequestMapping("/api/orders")
public class OrderController {
    private final OrderService orderService;
    private final CustomerService customerService;
    private final PaymentService paymentService;

    public OrderController(OrderService orderService, CustomerService customerService, PaymentService paymentService) {
        this.orderService = orderService;
        this.customerService = customerService;
        this.paymentService = paymentService;
    }

    @GetMapping
    public List<OrderDTO> listOrders() {
        return orderService.getAll();
    }

    @GetMapping("/{id}")
    public OrderDTO getOrder(@PathVariable Long id) {
        return orderService.getById(id).orElse(null);
    }

    @PostMapping
    public OrderDTO createOrder(@RequestBody OrderCreateRequest request) {
        return orderService.save(new OrderDTO(null, "ORD-1", request.totalAmount(), "PENDING"));
    }

    @PostMapping("/{id}/cancel")
    public void cancelOrder(@PathVariable Long id) {
        orderService.delete(id);
    }
}
"""

    files["src/main/java/com/example/app/controller/ProductController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.ProductService;
import com.example.app.service.CategoryService;
import com.example.app.dto.ProductDTO;
import com.example.app.dto.ProductCreateRequest;
import java.util.List;

@RestController
@RequestMapping("/api/products")
public class ProductController {
    private final ProductService productService;
    private final CategoryService categoryService;

    public ProductController(ProductService productService, CategoryService categoryService) {
        this.productService = productService;
        this.categoryService = categoryService;
    }

    @GetMapping
    public List<ProductDTO> listProducts() {
        return productService.getAll();
    }

    @GetMapping("/{id}")
    public ProductDTO getProduct(@PathVariable Long id) {
        return productService.getById(id).orElse(null);
    }

    @PostMapping
    public ProductDTO createProduct(@RequestBody ProductCreateRequest request) {
        return productService.save(new ProductDTO(null, request.name(), request.price(), request.sku()));
    }

    @DeleteMapping("/{id}")
    public void deleteProduct(@PathVariable Long id) {
        productService.delete(id);
    }
}
"""

    files["src/main/java/com/example/app/controller/CustomerController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.CustomerService;
import com.example.app.service.AddressService;
import com.example.app.dto.CustomerDTO;
import java.util.List;

@RestController
@RequestMapping("/api/customers")
public class CustomerController {
    private final CustomerService customerService;
    private final AddressService addressService;

    public CustomerController(CustomerService customerService, AddressService addressService) {
        this.customerService = customerService;
        this.addressService = addressService;
    }

    @GetMapping
    public List<CustomerDTO> listCustomers() {
        return customerService.getAll();
    }

    @GetMapping("/{id}")
    public CustomerDTO getCustomer(@PathVariable Long id) {
        return customerService.getById(id).orElse(null);
    }

    @PostMapping
    public CustomerDTO createCustomer(@RequestBody CustomerDTO dto) {
        return customerService.save(dto);
    }

    @DeleteMapping("/{id}")
    public void deleteCustomer(@PathVariable Long id) {
        customerService.delete(id);
    }
}
"""

    files["src/main/java/com/example/app/controller/InvoiceController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.InvoiceService;
import com.example.app.service.PaymentService;
import com.example.app.dto.InvoiceDTO;
import java.util.List;

@RestController
@RequestMapping("/api/invoices")
public class InvoiceController {
    private final InvoiceService invoiceService;
    private final PaymentService paymentService;

    public InvoiceController(InvoiceService invoiceService, PaymentService paymentService) {
        this.invoiceService = invoiceService;
        this.paymentService = paymentService;
    }

    @GetMapping
    public List<InvoiceDTO> listInvoices() {
        return invoiceService.getAll();
    }

    @GetMapping("/{id}")
    public InvoiceDTO getInvoice(@PathVariable Long id) {
        return invoiceService.getById(id).orElse(null);
    }

    @PostMapping
    public InvoiceDTO createInvoice(@RequestBody InvoiceDTO dto) {
        return invoiceService.save(dto);
    }
}
"""

    files["src/main/java/com/example/app/controller/PaymentController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.PaymentService;
import com.example.app.service.OrderService;
import com.example.app.dto.PaymentDTO;
import com.example.app.dto.PaymentRequest;
import java.util.List;

@RestController
@RequestMapping("/api/payments")
public class PaymentController {
    private final PaymentService paymentService;
    private final OrderService orderService;

    public PaymentController(PaymentService paymentService, OrderService orderService) {
        this.paymentService = paymentService;
        this.orderService = orderService;
    }

    @GetMapping
    public List<PaymentDTO> listPayments() {
        return paymentService.getAll();
    }

    @GetMapping("/{id}")
    public PaymentDTO getPayment(@PathVariable Long id) {
        return paymentService.getById(id).orElse(null);
    }

    @PostMapping
    public PaymentDTO makePayment(@RequestBody PaymentRequest request) {
        return paymentService.save(new PaymentDTO(null, "TX-1", request.amount(), request.paymentMethod()));
    }

    @PostMapping("/{id}/refund")
    public void refundPayment(@PathVariable Long id) {
        paymentService.delete(id);
    }
}
"""

    files["src/main/java/com/example/app/controller/NotificationController.java"] = """package com.example.app.controller;

import org.springframework.web.bind.annotation.*;
import com.example.app.service.NotificationService;
import com.example.app.service.UserService;
import com.example.app.dto.NotificationDTO;
import java.util.List;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {
    private final NotificationService notificationService;
    private final UserService userService;

    public NotificationController(NotificationService notificationService, UserService userService) {
        this.notificationService = notificationService;
        this.userService = userService;
    }

    @GetMapping
    public List<NotificationDTO> listNotifications() {
        return notificationService.getAll();
    }

    @GetMapping("/{id}")
    public NotificationDTO getNotification(@PathVariable Long id) {
        return notificationService.getById(id).orElse(null);
    }

    @PostMapping
    public NotificationDTO sendNotification(@RequestBody NotificationDTO dto) {
        return notificationService.save(dto);
    }
}
"""

    # 9. Config, Security & Helpers (9 types)
    files["src/main/java/com/example/app/config/SecurityConfig.java"] = """package com.example.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;

@Configuration
@EnableWebSecurity
public class SecurityConfig {
}
"""

    files["src/main/java/com/example/app/config/JwtTokenProvider.java"] = """package com.example.app.config;

import org.springframework.stereotype.Component;

@Component
public class JwtTokenProvider {
    public String generateToken(String username) {
        return "mock.jwt.token";
    }

    public boolean validateToken(String token) {
        return true;
    }
}
"""

    files["src/main/java/com/example/app/config/JwtAuthenticationFilter.java"] = """package com.example.app.config;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    private final JwtTokenProvider jwtTokenProvider;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }
}
"""

    files["src/main/java/com/example/app/config/CustomUserDetailsService.java"] = """package com.example.app.config;

import org.springframework.stereotype.Service;
import org.springframework.security.core.userdetails.UserDetailsService;
import com.example.app.repository.UserRepository;

@Service
public class CustomUserDetailsService implements UserDetailsService {
    private final UserRepository userRepository;

    public CustomUserDetailsService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }
}
"""

    files["src/main/java/com/example/app/config/SwaggerConfig.java"] = """package com.example.app.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {
}
"""

    files["src/main/java/com/example/app/config/WebMvcConfig.java"] = """package com.example.app.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class WebMvcConfig {
}
"""

    files["src/main/java/com/example/app/config/GlobalExceptionHandler.java"] = """package com.example.app.config;

import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {
}
"""

    files["src/main/java/com/example/app/helper/AuditLogHelper.java"] = """package com.example.app.helper;

import org.springframework.stereotype.Component;
import com.example.app.repository.AuditLogRepository;

@Component
public class AuditLogHelper {
    private final AuditLogRepository auditLogRepository;

    public AuditLogHelper(AuditLogRepository auditLogRepository) {
        this.auditLogRepository = auditLogRepository;
    }
}
"""

    files["src/main/java/com/example/app/helper/NotificationHelper.java"] = """package com.example.app.helper;

import org.springframework.stereotype.Component;
import com.example.app.repository.NotificationRepository;

@Component
public class NotificationHelper {
    private final NotificationRepository notificationRepository;

    public NotificationHelper(NotificationRepository notificationRepository) {
        this.notificationRepository = notificationRepository;
    }
}
"""

    return files


def create_large_project_dir(target_dir: str) -> str:
    """Writes the large synthetic Spring Boot project to disk in target_dir."""
    files = generate_large_project_files()
    for rel_path, content in files.items():
        full_path = os.path.join(target_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return target_dir


def create_large_project_zip_bytes() -> bytes:
    """Creates an in-memory ZIP archive of the large synthetic Spring Boot project."""
    files = generate_large_project_files()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files.items():
            zf.writestr(rel_path, content)
    buf.seek(0)
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="large_spring_project_")
    create_large_project_dir(out_dir)
    print(f"Large project generated in: {out_dir}")
