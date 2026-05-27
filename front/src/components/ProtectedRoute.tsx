import { Navigate, Outlet, useLocation } from "react-router-dom";

interface ProtectedRouteProps {
  token: string | null;
}

export default function ProtectedRoute({ token }: ProtectedRouteProps) {
  const location = useLocation();

  // Check if user has a valid token
  if (!token) {
    // Redirect to login page, but save the attempted location
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // User is authenticated, render the child routes
  return <Outlet />;
}
