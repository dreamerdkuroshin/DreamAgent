import { z } from "zod";

// Agents
export const CreateAgentBody = z.object({
  name: z.string(),
  description: z.string().optional(),
  model: z.string().optional(),
  systemPrompt: z.string().optional(),
});
export const UpdateAgentBody = CreateAgentBody.partial();
export const GetAgentParams = z.object({ id: z.number() });
export const UpdateAgentParams = z.object({ id: z.number() });
export const DeleteAgentParams = z.object({ id: z.number() });

// Conversations
export const CreateConversationBody = z.object({
  agentId: z.number(),
  title: z.string(),
});
export const ListConversationsQueryParams = z.object({
  agentId: z.number().optional(),
});
export const SendMessageBody = z.object({
  content: z.string(),
  mode: z.string().optional(), // Gap fix 4
});
export const SendMessageParams = z.object({ id: z.number() });
export const ListMessagesParams = z.object({ id: z.number() });

// Tasks
export const CreateTaskBody = z.object({
  agentId: z.number(),
  title: z.string(),
  description: z.string().optional(),
  priority: z.string().optional(),
});
export const UpdateTaskBody = z.object({
  status: z.string().optional(),
  title: z.string().optional(),
  description: z.string().optional(),
  priority: z.string().optional(),
  result: z.string().optional(),
});
export const GetTaskParams = z.object({ id: z.number() });
export const UpdateTaskParams = z.object({ id: z.number() });
export const ListTasksQueryParams = z.object({
    agentId: z.number().optional(),
    status: z.string().optional(),
});

// Health
export const HealthCheckResponse = z.object({
  status: z.string(),
  version: z.string(),
});
