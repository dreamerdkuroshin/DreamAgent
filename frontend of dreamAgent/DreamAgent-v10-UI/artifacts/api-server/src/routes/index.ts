import { Router, type IRouter } from "express";
import healthRouter from "./health";
import agentsRouter from "./agents";
import tasksRouter from "./tasks";
import conversationsRouter from "./conversations";
import statsRouter from "./stats";

const router: IRouter = Router();

router.use(healthRouter);
router.use(agentsRouter);
router.use(tasksRouter);
router.use(conversationsRouter);
router.use(statsRouter);

export default router;
