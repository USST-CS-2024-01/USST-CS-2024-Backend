from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select
from middleware.auth import need_login
from model import ClassMember, TeacherScore
from model.enum import UserType
from model.response_model import (
    BaseListResponse,
    ErrorResponse,
)
from model.schema import UserSchema
from service.class_ import has_class_access

score_bp = Blueprint("score")


@score_bp.route("/class/<class_id:int>/score/list", methods=["GET"])
@openapi.summary("获取班级成绩列表")
@openapi.tag("成绩接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_score_list(request, class_id: int):
    db = request.app.ctx.db
    user = request.ctx.user

    if class_id == 1:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    with db() as session:
        user_list_stmt = select(ClassMember).where(
            ClassMember.class_id.__eq__(class_id),
            ClassMember.is_teacher.is_(False),
        )
        if user.user_type == UserType.student:
            user_list_stmt = user_list_stmt.where(ClassMember.user_id == user.id)

        user_result = session.execute(user_list_stmt).scalars().all()
        stmt = select(TeacherScore).where(
            TeacherScore.user_id.in_(user.user_id for user in user_result),
        )
        result = session.execute(stmt).scalars().all()

        score_dict = {}
        user_dict = {}
        for item in result:
            if item.task.class_id != class_id:
                continue

            key = item.user.id
            if key not in score_dict:
                score_dict[key] = []

            score_dict[key].append(
                {
                    "task": {
                        "id": item.task.id,
                        "name": item.task.name,
                        "grade_percentage": item.task.grade_percentage,
                    },
                    "score": item.score,
                    "score_details": item.score_details,
                }
            )

        for item in user_result:
            user_dict[item.user.id] = UserSchema.model_validate(item.user)

        score_list = []
        for key in user_dict:
            score_list.append(
                {"user": user_dict[key], "score": score_dict.get(key, [])}
            )
            item = score_list[-1]
            item["total_score"] = sum(
                [
                    score["score"] * score["task"]["grade_percentage"] / 100
                    for score in item["score"]
                ]
            )

        return BaseListResponse(
            data=score_list,
            total=len(score_list),
            page=1,
            page_size=len(score_list),
        ).json_response()
