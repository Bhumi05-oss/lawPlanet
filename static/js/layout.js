/* LawPlanet - shared sidebar layout for logged-in pages */

function clientNavLinks(active) {
  const links = [
    { href: "/dashboard-client.html", key: "dashboard", icon: "🏠", label: "Dashboard" },
    { href: "/find-lawyers.html", key: "find", icon: "🔍", label: "Find Lawyers" },
    { href: "/chats.html", key: "chats", icon: "💬", label: "My Chats" },
    { href: "/my-profile.html", key: "profile", icon: "👤", label: "My Profile" },
  ];
  return links;
}

function lawyerNavLinks(active) {
  const links = [
    { href: "/dashboard-lawyer.html", key: "dashboard", icon: "🏠", label: "Dashboard" },
    { href: "/my-cases.html", key: "cases", icon: "📁", label: "My Cases" },
    { href: "/chats.html", key: "chats", icon: "💬", label: "Client Chats" },
    { href: "/lawyer-profile-edit.html", key: "lawyerprofile", icon: "⚖️", label: "Lawyer Profile" },
    { href: "/my-profile.html", key: "profile", icon: "👤", label: "My Profile" },
  ];
  return links;
}

async function renderSidebar(activeKey) {
  const user = Auth.getUser();
  if (!user) return;
  const links = user.role === "lawyer" ? lawyerNavLinks(activeKey) : clientNavLinks(activeKey);

  let unread = 0;
  try {
    const convs = await api("/api/conversations");
    unread = convs.reduce((sum, c) => sum + (c.unread_count || 0), 0);
  } catch (e) { /* ignore */ }

  const navHtml = links.map(l => {
    const badge = (l.key === "chats" && unread > 0) ? `<span class="badge-count">${unread}</span>` : "";
    return `<a class="nav-link ${l.key === activeKey ? 'active' : ''}" href="${l.href}">${l.icon} ${l.label} ${badge}</a>`;
  }).join("");

  const html = `
    <div class="brand">🏛️ Law<span class="gold">Planet</span></div>
    <nav>${navHtml}</nav>
    <div class="sidebar-footer">
      <div class="sidebar-user">
        <div class="avatar" style="background:${user.avatar_color || '#0f3d5c'}">${initials(user.full_name)}</div>
        <div>
          <div class="sidebar-user-name">${escapeHtml(user.full_name)}</div>
          <div class="sidebar-user-role">${user.role}</div>
        </div>
      </div>
      <button class="btn btn-outline-light btn-sm btn-block" onclick="Auth.logout()">Log Out</button>
    </div>
  `;
  document.querySelectorAll(".sidebar").forEach(el => el.innerHTML = html);
}
