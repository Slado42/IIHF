/**
 * Tests for Login and Signup pages.
 *
 * These pages use AuthContext (which calls api/client).  We mock the entire
 * api/client module so no real HTTP calls are made, and provide a minimal
 * AuthProvider wrapper that reads from the mocked functions.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import Login from "../pages/Login";
import Signup from "../pages/Signup";

// ---------------------------------------------------------------------------
// Mock api/client
// ---------------------------------------------------------------------------
vi.mock("../api/client", () => ({
  login: vi.fn(),
  signup: vi.fn(),
  getMe: vi.fn(),
  getPlayers: vi.fn(),
  getTodaysMatches: vi.fn(),
  getMyLineup: vi.fn(),
  saveLineup: vi.fn(),
  getStandings: vi.fn(),
  getMyScores: vi.fn(),
}));

import * as apiClient from "../api/client";
const mockedLogin = vi.mocked(apiClient.login);
const mockedSignup = vi.mocked(apiClient.signup);
const mockedGetMe = vi.mocked(apiClient.getMe);

// Wrapper that provides Router + AuthContext
function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: getMe resolves (called in AuthProvider on mount when token exists)
    mockedGetMe.mockResolvedValue({ data: { id: "u1", username: "testuser", email: "t@t.com", created_at: "" } } as any);
  });

  it("renders username and password labels and a submit button", () => {
    render(
      <Wrapper>
        <Login />
      </Wrapper>
    );
    expect(screen.getByText(/username/i)).toBeInTheDocument();
    expect(screen.getByText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls login API when the form is submitted", async () => {
    const user = userEvent.setup();
    mockedLogin.mockResolvedValueOnce({ data: { access_token: "fake-token" } } as any);
    mockedGetMe.mockResolvedValue({ data: { id: "u1", username: "testuser", email: "t@t.com", created_at: "" } } as any);

    render(
      <Wrapper>
        <Login />
      </Wrapper>
    );

    const inputs = screen.getAllByRole("textbox");
    // First visible textbox is username
    await user.type(inputs[0], "testuser");

    // Password field (type="password") is not a textbox role; use placeholder or label
    const pwdInput = document.querySelector('input[type="password"]') as HTMLInputElement;
    await user.type(pwdInput, "password123");

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockedLogin).toHaveBeenCalledWith("testuser", "password123");
    });
  });
});

describe("SignupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetMe.mockResolvedValue({ data: { id: "u1", username: "newuser", email: "n@n.com", created_at: "" } } as any);
  });

  it("renders username, email, and password fields", () => {
    render(
      <Wrapper>
        <Signup />
      </Wrapper>
    );
    expect(screen.getByText(/username/i)).toBeInTheDocument();
    expect(screen.getByText(/email/i)).toBeInTheDocument();
    expect(screen.getByText(/password/i)).toBeInTheDocument();
  });

  it("calls signup API when the form is submitted with valid data", async () => {
    const user = userEvent.setup();
    mockedSignup.mockResolvedValueOnce({ data: { access_token: "fake-token" } } as any);
    mockedGetMe.mockResolvedValue({ data: { id: "u1", username: "newuser", email: "n@n.com", created_at: "" } } as any);

    render(
      <Wrapper>
        <Signup />
      </Wrapper>
    );

    const textInputs = screen.getAllByRole("textbox");
    // textInputs: username, email (password is type=password so not textbox role)
    await user.type(textInputs[0], "newuser");
    await user.type(textInputs[1], "new@example.com");

    const pwdInput = document.querySelector('input[type="password"]') as HTMLInputElement;
    await user.type(pwdInput, "securepass");

    await user.click(screen.getByRole("button", { name: /sign up/i }));

    await waitFor(() => {
      expect(mockedSignup).toHaveBeenCalledWith("newuser", "new@example.com", "securepass");
    });
  });
});
