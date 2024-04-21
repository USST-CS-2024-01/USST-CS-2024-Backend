from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select, and_

import service.class_
import service.file
import service.group
import service.group_meeting
import service.group_task
import service.role
import service.task
from controller.v1.group_member_score.request_model import CreateGroupMemberScoreRequest
from middleware.auth import need_login
from middleware.validator import validate
from model import TaskGroupMemberScore, UserType
from model.response_model import (
    ErrorResponse,
    BaseDataResponse,
)
from model.schema import TaskGroupMemberScoreSchema

group_member_score_bp = Blueprint("group_member_score")


@group_member_score_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/group_score",
    methods=["GET"],
)
@openapi.summary("获取组内成员互评分数")
@openapi.tag("组内互评接口")
@need_login()
async def get_group_member_score(request, class_id: int, group_id: int, task_id: int):
    """
    获取组内成员互评分数
    """
    db = request.app.ctx.db
    user = request.ctx.user

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        stmt = select(TaskGroupMemberScore).where(
            and_(
                TaskGroupMemberScore.task_id == task_id,
                TaskGroupMemberScore.group_id == group_id,
            )
        )
        scores = session.execute(stmt).scalar()
        if not scores:
            return ErrorResponse.new_error(
                code=404,
                message="Scores not found",
            )

        # 学生只能看到自己的评分
        if user.user_type == UserType.student:
            if is_manager:
                scores.group_manager_score = {}  # 隐藏组长评分
            else:
                scores.group_member_scores = {}  # 隐藏组员评分
                scores.group_manager_score = {
                    str(user.id): scores.group_manager_score.get(str(user.id), 0)
                }

        return BaseDataResponse(
            data=TaskGroupMemberScoreSchema.model_validate(scores)
        ).json_response()


@group_member_score_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/group_score",
    methods=["POST"],
)
@openapi.summary("提交组内成员互评分数")
@openapi.tag("组内互评接口")
@need_login()
@validate(json=CreateGroupMemberScoreRequest)
async def create_group_member_score(
    request,
    class_id: int,
    group_id: int,
    task_id: int,
    body: CreateGroupMemberScoreRequest,
):
    db = request.app.ctx.db
    user = request.ctx.user

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    score_map = body.score_map
    for v in score_map.values():
        if v < 0 or v > 100:
            return ErrorResponse.new_error(
                code=400,
                message="Score should be in range [0, 100]",
            )

    with db() as session:
        session.add(group)
        group_member_ids = [m.user_id for m in group.members]

        score = (
            session.query(TaskGroupMemberScore)
            .filter(
                TaskGroupMemberScore.task_id == task_id,
                TaskGroupMemberScore.group_id == group_id,
            )
            .first()
        )
        found = False
        if not score:
            score = TaskGroupMemberScore(
                task_id=task_id,
                group_id=group_id,
                group_manager_score={},
                group_member_scores={},
            )
        else:
            found = True

        group_manager_id = service.group.get_group_manager_user_id(
            request, class_id, group_id
        )

        if is_manager:
            if group_manager_id in score_map:
                return ErrorResponse.new_error(
                    code=400,
                    message="You can't score yourself",
                )

            member_id_set = set(group_member_ids)
            score_id_set = set(map(int, score_map.keys()))

            if not score_id_set.issubset(member_id_set):
                return ErrorResponse.new_error(
                    code=400,
                    message="You can only score group members",
                )

            update_map = {str(k): v for k, v in score_map.items()}
            score.group_member_scores.update(update_map)
        else:
            if group_manager_id not in score_map or len(score_map) != 1:
                return ErrorResponse.new_error(
                    code=400,
                    message="You can only score group manager",
                )
            score.group_manager_score.update(
                {str(user.id): score_map[group_manager_id]}
            )

        if not found:
            session.add(score)
        else:
            session.merge(score)

        session.commit()

        return BaseDataResponse().json_response()
