"use client"

import * as React from "react"
import { Search, Plus, MoreHorizontal, Shield, ShieldCheck, Pencil, Trash2, Check, X, Eye, EyeOff } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import { accessManagementApi, AdminUser } from "@/lib/api"

interface User {
  id: string
  name: string
  email: string
  role: "admin" | "sme"
  status: "active" | "inactive"
  lastActive: string
}

const mockUsers: User[] = [
  { id: "1", name: "Admin User", email: "admin@durranis.com", role: "admin", status: "active", lastActive: "Just now" },
]

const rolePermissions = {
  admin: {
    label: "Admin",
    description: "Full access to all features",
    permissions: [
      "Upload Documents",
      "Upload Videos",
      "Upload Model Papers",
      "Generate Notes",
      "Generate Predictions",
      "AI Assistant",
      "Manage Prompt Templates",
      "View Directory",
      "Manage Users",
    ],
  },
  sme: {
    label: "SME (Subject Matter Expert)",
    description: "Limited access for content creation",
    permissions: ["Upload Documents", "Upload Videos", "Upload Model Papers", "Generate Notes", "AI Assistant"],
  },
}

export function AccessManagementView() {
  const [users, setUsers] = React.useState<User[]>([])
  const [searchQuery, setSearchQuery] = React.useState("")
  const [addUserOpen, setAddUserOpen] = React.useState(false)
  const [editUser, setEditUser] = React.useState<User | null>(null)
  const [newUser, setNewUser] = React.useState({ name: "", email: "", password: "", role: "sme" as "admin" | "sme" })
  const [showNewPassword, setShowNewPassword] = React.useState(false)
  const [showEditPassword, setShowEditPassword] = React.useState(false)
  const { toast } = useToast()

  const mapApiUserToUser = React.useCallback((apiUser: AdminUser): User => {
    const joinedLabel = apiUser.joined_date ? `Joined ${new Date(apiUser.joined_date).toLocaleDateString()}` : ""

    const roleValue = apiUser.role?.toLowerCase() || ""
    const uiRole: "admin" | "sme" =
      roleValue === "admin"
        ? "admin"
        : roleValue === "sme"
          ? "sme"
          : roleValue.startsWith("admin")
            ? "admin"
            : "sme"

    return {
      id: String(apiUser.id),
      name: apiUser.name,
      email: apiUser.email,
      role: uiRole,
      status: apiUser.status === "inactive" ? "inactive" : "active",
      lastActive: joinedLabel,
    }
  }, [])

  React.useEffect(() => {
    const loadUsers = async () => {
      try {
        const apiUsers = await accessManagementApi.getUsers()
        if (Array.isArray(apiUsers) && apiUsers.length > 0) {
          setUsers(apiUsers.map(mapApiUserToUser))
        } else {
          setUsers(mockUsers)
        }
      } catch (error) {
        console.error("Failed to load admin users", error)
        setUsers(mockUsers)
      }
    }

    loadUsers()
  }, [mapApiUserToUser])

  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  const handleAddUser = async () => {
    if (!newUser.name.trim()) {
      toast({ title: "Validation Error", description: "Full name is required", variant: "destructive" })
      return
    }
    if (!newUser.email.trim()) {
      toast({ title: "Validation Error", description: "Email is required", variant: "destructive" })
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newUser.email)) {
      toast({ title: "Validation Error", description: "Please enter a valid email address", variant: "destructive" })
      return
    }
    if (!newUser.password.trim()) {
      toast({ title: "Validation Error", description: "Password is required", variant: "destructive" })
      return
    }

    try {
      const created = await accessManagementApi.addUser({
        name: newUser.name,
        email: newUser.email,
        password: newUser.password,
        role: newUser.role,
      })

      const user = mapApiUserToUser(created)
      user.lastActive = "Just now"

      setUsers([...users, user])
      setAddUserOpen(false)
      setNewUser({ name: "", email: "", password: "", role: "sme" })
      toast({
        title: "User added successfully",
        description: `${user.name} has been added as ${user.role === "admin" ? "Admin" : "SME"}.`,
      })
    } catch (error: any) {
      toast({
        title: "Error adding user",
        description: error?.message || "Failed to add user. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleUpdateUser = async () => {
    if (!editUser) return
    if (!editUser.name.trim()) {
      toast({ title: "Validation Error", description: "Full name is required", variant: "destructive" })
      return
    }
    if (!editUser.email.trim()) {
      toast({ title: "Validation Error", description: "Email is required", variant: "destructive" })
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(editUser.email)) {
      toast({ title: "Validation Error", description: "Please enter a valid email address", variant: "destructive" })
      return
    }

    try {
      const payload: any = {
        name: editUser.name,
        email: editUser.email,
        role: editUser.role,
      }

      const newPassword = (editUser as any).password
      if (newPassword && newPassword.trim().length > 0) {
        payload.password = newPassword
      }

      const updated = await accessManagementApi.updateUser(Number(editUser.id), payload)
      const mapped = mapApiUserToUser(updated)

      setUsers(users.map((u) => (u.id === mapped.id ? mapped : u)))
      setEditUser(null)
      toast({ title: "User updated successfully", description: `${mapped.name}'s details have been saved.` })
    } catch (error: any) {
      toast({
        title: "Error updating user",
        description: error?.message || "Failed to update user. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleDeleteUser = async (user: User) => {
    try {
      await accessManagementApi.deleteUser(Number(user.id))
      setUsers(users.filter((u) => u.id !== user.id))
      toast({
        title: "User removed successfully",
        description: `${user.name} has been removed from the system.`,
        variant: "destructive",
      })
    } catch (error: any) {
      toast({
        title: "Error removing user",
        description: error?.message || "Failed to remove user. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleToggleStatus = async (user: User) => {
    const newStatus = user.status === "active" ? "inactive" : "active"
    try {
      await accessManagementApi.updateUser(Number(user.id), { status: newStatus })
      setUsers(users.map((u) => (u.id === user.id ? { ...u, status: newStatus } : u)))
      toast({
        title: newStatus === "active" ? "User activated" : "User deactivated",
        description: `${user.name} is now ${newStatus}.`,
      })
    } catch (error: any) {
      toast({
        title: "Error updating status",
        description: error?.message || "Failed to update user status. Please try again.",
        variant: "destructive",
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Access Management</h1>
          <p className="text-neutral-500 mt-1">Manage users and their permissions</p>
        </div>
        <Button onClick={() => setAddUserOpen(true)} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
          <Plus className="h-4 w-4 mr-2" />
          Add User
        </Button>
      </div>

      {/* Role Permissions Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(rolePermissions).map(([key, role]) => (
          <div key={key} className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              {key === "admin" ? (
                <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
                  <ShieldCheck className="h-5 w-5 text-amber-600" />
                </div>
              ) : (
                <div className="h-10 w-10 rounded-lg bg-[#27C3F2]/10 flex items-center justify-center">
                  <Shield className="h-5 w-5 text-[#0294D0]" />
                </div>
              )}
              <div>
                <h3 className="font-semibold text-neutral-900">{role.label}</h3>
                <p className="text-sm text-neutral-500">{role.description}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {role.permissions.map((perm) => (
                <span
                  key={perm}
                  className={cn(
                    "text-xs px-2 py-1 rounded-full",
                    key === "admin" ? "bg-amber-50 text-amber-700" : "bg-[#27C3F2]/10 text-[#006A93]",
                  )}
                >
                  {perm}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
        <Input
          placeholder="Search users..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          autoComplete="off"
          className="pl-10 h-10 bg-white border-neutral-200"
        />
      </div>

      {/* Users Table */}
      <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/50">
                <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-4 py-3">
                  User
                </th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-4 py-3">
                  Role
                </th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-4 py-3 hidden sm:table-cell">
                  Status
                </th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-4 py-3 hidden md:table-cell">
                  Last Active
                </th>
                <th className="text-right text-xs font-medium text-neutral-500 uppercase tracking-wider px-4 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filteredUsers.map((user) => (
                <tr key={user.id} className="hover:bg-neutral-50/50 transition-colors">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-neutral-900">{user.name}</p>
                      <p className="text-sm text-neutral-500">{user.email}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full",
                        user.role === "admin" ? "bg-amber-100 text-amber-700" : "bg-[#27C3F2]/10 text-[#006A93]",
                      )}
                    >
                      {user.role === "admin" ? <ShieldCheck className="h-3 w-3" /> : <Shield className="h-3 w-3" />}
                      {user.role === "admin" ? "Admin" : "SME"}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full",
                        user.status === "active"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-neutral-100 text-neutral-500",
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          user.status === "active" ? "bg-emerald-500" : "bg-neutral-400",
                        )}
                      />
                      {user.status === "active" ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className="text-sm text-neutral-500">{user.lastActive}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuItem onClick={() => setEditUser(user)}>
                          <Pencil className="h-4 w-4 mr-2" />
                          Edit User
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleToggleStatus(user)}>
                          {user.status === "active" ? (
                            <>
                              <X className="h-4 w-4 mr-2" />
                              Deactivate
                            </>
                          ) : (
                            <>
                              <Check className="h-4 w-4 mr-2" />
                              Activate
                            </>
                          )}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => handleDeleteUser(user)} className="text-red-600">
                          <Trash2 className="h-4 w-4 mr-2" />
                          Remove User
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add User Dialog */}
      <Dialog open={addUserOpen} onOpenChange={setAddUserOpen}>
        <DialogContent className="sm:max-w-[425px] [&>button]:hidden">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle>Add New User</DialogTitle>
              <button
                onClick={() => setAddUserOpen(false)}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Full Name</Label>
              <Input
                value={newUser.name}
                onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                placeholder="Enter full name"
                className="h-10"
              />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                placeholder="Enter email address"
                className="h-10"
              />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <div className="relative">
                <Input
                  type={showNewPassword ? "text" : "password"}
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  placeholder="Enter password"
                  autoComplete="new-password"
                  className="h-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
                >
                  {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select
                value={newUser.role}
                onValueChange={(value: "admin" | "sme") => setNewUser({ ...newUser, role: value })}
              >
                <SelectTrigger className="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin - Full Access</SelectItem>
                  <SelectItem value="sme">SME - Limited Access</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setAddUserOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddUser} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
              Add User
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={!!editUser} onOpenChange={() => setEditUser(null)}>
        <DialogContent className="sm:max-w-[425px] [&>button]:hidden">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle>Edit User</DialogTitle>
              <button
                onClick={() => setEditUser(null)}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </DialogHeader>
          {editUser && (
            <>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Full Name</Label>
                  <Input
                    value={editUser.name}
                    onChange={(e) => setEditUser({ ...editUser, name: e.target.value })}
                    className="h-10"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={editUser.email}
                    onChange={(e) => setEditUser({ ...editUser, email: e.target.value })}
                    className="h-10"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Password</Label>
                  <div className="relative">
                    <Input
                      type={showEditPassword ? "text" : "password"}
                      value={(editUser as any).password || ""}
                      onChange={(e) => setEditUser({ ...editUser, password: e.target.value } as any)}
                      placeholder="Enter new password"
                      autoComplete="new-password"
                      className="h-10 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowEditPassword(!showEditPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
                    >
                      {showEditPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Role</Label>
                  <Select
                    value={editUser.role}
                    onValueChange={(value: "admin" | "sme") => setEditUser({ ...editUser, role: value })}
                  >
                    <SelectTrigger className="h-10">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin - Full Access</SelectItem>
                      <SelectItem value="sme">SME - Limited Access</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setEditUser(null)}>
                  Cancel
                </Button>
                <Button onClick={handleUpdateUser} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
                  Save Changes
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
