-- 数据库初始化脚本
-- 创建评论表的索引和约束

-- 确保数据库存在
CREATE DATABASE IF NOT EXISTS comment_db;

-- 使用数据库
\c comment_db;

-- 创建评论表（如果SQLAlchemy没有自动创建的话）
-- 这个脚本主要用于添加额外的索引和约束

-- 添加复合索引以优化查询性能
DO $$ 
BEGIN
    -- 检查表是否存在
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'comments') THEN
        
        -- 为页面和创建时间创建复合索引
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_page_created_at') THEN
            CREATE INDEX CONCURRENTLY idx_page_created_at ON comments(page, created_at DESC);
        END IF;
        
        -- 为父评论ID和创建时间创建复合索引
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_parent_created_at') THEN
            CREATE INDEX CONCURRENTLY idx_parent_created_at ON comments(parent_id, created_at DESC) WHERE parent_id IS NOT NULL;
        END IF;
        
        -- 为活跃评论创建部分索引
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_active_comments') THEN
            CREATE INDEX CONCURRENTLY idx_active_comments ON comments(page, parent_id, created_at DESC) WHERE is_deleted = false;
        END IF;
        
        RAISE NOTICE 'Additional indexes created successfully';
    ELSE
        RAISE NOTICE 'Comments table does not exist yet, will be created by application';
    END IF;
END $$;