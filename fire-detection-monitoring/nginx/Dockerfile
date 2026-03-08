# nginx/Dockerfile
# Nginx server để serve images
#
# Build:
#   docker build -t fire-nginx .
#
# Run standalone:
#   docker run -d --name nginx \
#     -p 8080:80 \
#     -v $(pwd)/../images:/usr/share/nginx/html/images:ro \
#     fire-nginx

FROM nginx:alpine

# Copy configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create images directory
RUN mkdir -p /usr/share/nginx/html/images

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/images/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
